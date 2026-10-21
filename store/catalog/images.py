"""Managed product image generations. Shop logos and videos are never touched."""
import hashlib
import io
import ipaddress
import logging
import shutil
import socket
import uuid
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image, ImageOps
from django.conf import settings

logger = logging.getLogger(__name__)


def image_root():
    root = Path(settings.MEDIA_ROOT).resolve() / "product-images"
    root.mkdir(parents=True, exist_ok=True)
    return root


def remove_managed(path):
    root = image_root().resolve()
    path = Path(path)
    if path.is_symlink():
        if path.parent.resolve() == root:
            path.unlink()
        return
    resolved = path.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError("مسیر حذف تصویر خارج از پوشه محصولات است.")
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def prune_images(keep_generation):
    for path in image_root().iterdir():
        if path.name not in {keep_generation, "custom"}:
            remove_managed(path)


@contextmanager
def catalog_sync_lock():
    lock_path = Path(settings.MEDIA_ROOT).resolve() / ".catalog-sync.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    try:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if __import__("os").name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("بروزرسانی دیگری در حال اجراست. کمی بعد دوباره تلاش کنید.") from exc
        yield
    finally:
        # Closing the file also releases the OS lock, including exception paths.
        handle.close()


def _validate_remote_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("نشانی تصویر معتبر نیست.")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    if any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("نشانی تصویر باید متعلق به سرور عمومی باشد.")


def download_image(url, *, client=None):
    limit = settings.PRODUCT_IMAGE_DOWNLOAD_LIMIT
    for _ in range(5):
        _validate_remote_url(url)
        headers = {"Accept": "image/*"}
        if client and urlparse(url).netloc == urlparse(client.base_url).netloc:
            headers["Authorization"] = "Bearer " + client.access_token
        with requests.get(url, headers=headers, stream=True, allow_redirects=False, timeout=(8, 25)) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers["Location"])
                continue
            response.raise_for_status()
            if int(response.headers.get("Content-Length", 0)) > limit:
                raise ValueError("حجم تصویر بیش از حد مجاز است.")
            output = io.BytesIO()
            for chunk in response.iter_content(65536):
                if output.tell() + len(chunk) > limit:
                    raise ValueError("حجم تصویر بیش از حد مجاز است.")
                output.write(chunk)
            return output.getvalue()
    raise ValueError("تعداد تغییر مسیر تصویر بیش از حد مجاز است.")


def encode_webp(content):
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(content)) as source:
            if source.width * source.height > 30_000_000:
                raise ValueError("ابعاد تصویر بیش از حد مجاز است.")
            image = ImageOps.exif_transpose(source)
            image.thumbnail((settings.PRODUCT_IMAGE_MAX_SIZE, settings.PRODUCT_IMAGE_MAX_SIZE), Image.Resampling.LANCZOS)
            image = image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB")
            output = io.BytesIO()
            # No EXIF, ICC profile or source metadata is copied into the output.
            image.save(output, format="WEBP", quality=settings.PRODUCT_IMAGE_WEBP_QUALITY, method=6)
            return output.getvalue()


def prepare_images(sources, *, client=None, progress=None):
    generation = "g-" + uuid.uuid4().hex
    directory = image_root() / generation
    directory.mkdir()
    results = {}
    errors = []

    def prepare(code, source):
        for attempt in range(3):
            try:
                raw = download_image(source, client=client)
                break
            except (requests.Timeout, requests.ConnectionError):
                if attempt == 2:
                    raise
                __import__('time').sleep(attempt + 1)
        data = encode_webp(raw)
        filename = hashlib.sha256(code.encode()).hexdigest()[:24] + ".webp"
        (directory / filename).write_bytes(data)
        return code, {"image_url": settings.MEDIA_URL.rstrip("/") + "/product-images/" + generation + "/" + filename, "image_source_url": source, "image_size": len(data)}

    try:
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="catalog-image") as executor:
            futures = {executor.submit(prepare, code, source): code for code, source in sources.items() if source}
            for future in as_completed(futures):
                code = futures[future]
                try:
                    product_code, result = future.result()
                    results[product_code] = result
                except Exception as exc:
                    if isinstance(exc, requests.HTTPError):
                        reason = "HTTP " + str(exc.response.status_code)
                    elif isinstance(exc, requests.Timeout):
                        reason = "مهلت دریافت تصویر تمام شد"
                    elif isinstance(exc, requests.ConnectionError):
                        reason = "اتصال به سرور تصویر برقرار نشد"
                    elif isinstance(exc, ValueError):
                        reason = str(exc)[:160]
                    else:
                        reason = "فایل تصویر معتبر نیست یا قابل تبدیل نیست"
                    errors.append({"code": code, "reason": reason})
                    logger.warning("Product image could not be optimized (code %s).", code)
                if progress:
                    progress(len(results) + len(errors), len(futures))
        return generation, results, errors
    except BaseException:
        remove_managed(directory)
        raise
