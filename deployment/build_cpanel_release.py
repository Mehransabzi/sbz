"""Build a private cPanel ZIP without changing the working database or .env."""
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.staticfiles import finders
from dotenv import dotenv_values


def cipher(secret):
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def build():
    release_secret = secrets.token_urlsafe(64)
    snapshot = sqlite3.connect(":memory:")
    source_path = Path(settings.DATABASES["default"]["NAME"]).resolve()
    with sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True) as source:
        source.backup(snapshot)

    old_cipher, new_cipher = cipher(settings.SECRET_KEY), cipher(release_secret)
    # The encryption of API keys is tied to SECRET_KEY. Re-encrypt only the
    # private archive snapshot so the production key can differ from local.
    table = "store_controlpanel_siteconfiguration"
    columns = ("ai_api_key_encrypted", "chortke_api_key_encrypted")
    for pk, ai_key, chortke_key in snapshot.execute(
        f"SELECT id, {', '.join(columns)} FROM {table}"
    ).fetchall():
        updated = []
        for encrypted in (ai_key, chortke_key):
            if encrypted:
                clear = old_cipher.decrypt(encrypted.encode())
                replacement = new_cipher.encrypt(clear).decode()
                if new_cipher.decrypt(replacement.encode()) != clear:
                    raise RuntimeError("API key re-encryption validation failed")
                updated.append(replacement)
            else:
                updated.append("")
        snapshot.execute(
            f"UPDATE {table} SET {columns[0]}=?, {columns[1]}=? WHERE id=?",
            (*updated, pk),
        )
    snapshot.commit()
    if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError("Snapshot database integrity check failed")
    database = snapshot.serialize()
    product_count = snapshot.execute("SELECT COUNT(*) FROM catalog_product").fetchone()[0]
    snapshot.close()

    env = {key: value for key, value in dotenv_values(ROOT / ".env").items() if value is not None}
    env.update({
        "DJANGO_SECRET_KEY": release_secret,
        "DJANGO_DEBUG": "false",
        "DJANGO_ALLOWED_HOSTS": "sbzpart.ir,www.sbzpart.ir",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://sbzpart.ir,https://www.sbzpart.ir",
        "DJANGO_SETTINGS_MODULE": "config.cpanel",
        "DJANGO_SECURE_SSL_REDIRECT": "false",
        "DJANGO_TRUST_PROXY_SSL_HEADER": "false",
    })
    # dotenv supports single-quoted values and escaped quotes/backslashes.
    env_text = "# Private production configuration for sbzpart.ir\n"
    for key, value in sorted(env.items()):
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        env_text += f"{key}='{escaped}'\n"

    release_dir = ROOT / "release"
    release_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive_path = release_dir / f"sbzpart-cpanel-{stamp}.zip"
    manifest = {}
    excluded = {"__pycache__", ".pytest_cache", ".git", ".idea", ".venv"}
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        def add(name, data, private=False):
            if name in manifest:
                return
            info = zipfile.ZipInfo(name, date_time=datetime.now().timetuple()[:6])
            info.create_system = 3
            info.external_attr = (0o100600 if private else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
            manifest[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

        for folder in ("config", "store", "templates"):
            for path in sorted((ROOT / folder).rglob("*")):
                relative = path.relative_to(ROOT)
                if not path.is_file() or path.is_symlink() or excluded.intersection(relative.parts):
                    continue
                if path.suffix in {".pyc", ".pyo", ".log", ".bak"}:
                    continue
                add(relative.as_posix(), path.read_bytes())
        for name in ("manage.py", "passenger_wsgi.py", "requirements.txt", "README.md", ".env.example", "CPANEL-SETUP.fa.md"):
            add(name, (ROOT / name).read_bytes())
        for path in sorted((ROOT / "media").rglob("*")):
            relative = path.relative_to(ROOT)
            if not path.is_file() or path.is_symlink() or "product-ai" in relative.parts or path.name.startswith("."):
                continue
            add(relative.as_posix(), path.read_bytes())
        # Collect static assets straight into the ZIP, including Django admin.
        for finder in finders.get_finders():
            for name, storage in finder.list([]):
                prefix = getattr(storage, "prefix", None)
                destination = "/".join(part for part in ("staticfiles", prefix, name.replace("\\", "/")) if part)
                with storage.open(name, "rb") as file:
                    add(destination, file.read())
        add("db.sqlite3", database, private=True)
        add(".env", env_text.encode(), private=True)
        static_rules = b"Options -Indexes\n<IfModule mod_passenger.c>\nPassengerEnabled off\n</IfModule>\n"
        add("staticfiles/.htaccess", static_rules)
        add("media/.htaccess", static_rules + b'<FilesMatch "(?i)\\.(php[0-9]?|phtml|phar|py|pl|cgi|sh|html?|svg|shtml)$">\nRequire all denied\n</FilesMatch>\n')
        metadata = {
            "domain": "sbzpart.ir", "created_utc": datetime.now(timezone.utc).isoformat(),
            "products": product_count, "files": manifest,
            "private_archive": True, "database": "consistent SQLite snapshot",
            "excluded": [".venv", ".idea", ".migration_backup", "__pycache__", "media/product-ai"],
        }
        add("RELEASE_INFO.json", json.dumps(metadata, ensure_ascii=False, indent=2).encode())

    with zipfile.ZipFile(archive_path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise RuntimeError(f"Invalid archive member: {bad_member}")
        for name, details in manifest.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != details["sha256"]:
                raise RuntimeError(f"Archive checksum mismatch: {name}")
    print(json.dumps({"archive": str(archive_path), "size_mb": round(archive_path.stat().st_size / 1048576, 2), "files": len(manifest), "products": product_count, "archive_integrity": "ok", "source_database_unchanged": True}))


if __name__ == "__main__":
    build()
