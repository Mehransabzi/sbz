from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

from django.core.cache import cache

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from store.catalog.models import Product
from store.catalog.images import catalog_sync_lock, prepare_images, prune_images, remove_managed, image_root
from store.catalog.search.indexing import rebuild_index

from .client import ChortkeClient
from .models import SyncRun


STOCK_FIELDS = (
    "stock", "quantity", "quantityAvailable", "availableQuantity", "stockCount",
    "inventory", "onHand", "onHandQuantity", "currentStock", "stockQuantity",
)


def decimal_value(value, *, divisor=Decimal("1")):
    try:
        return Decimal(str(value if value is not None else 0)) / divisor
    except (InvalidOperation, TypeError, ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"مقدار عددی نامعتبر از چرتکه: {value!r}") from exc


def first_value(record, *keys, default=None):
    for key in keys:
        value = record.get(key)
        if value is not None and value != "":
            return value
    return default


def stock_value(record):
    """Return a recognized stock field even when the API nests it in a product payload."""
    wanted = {key.casefold() for key in STOCK_FIELDS}

    def find(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                if str(key).casefold() in wanted and nested is not None and not isinstance(nested, (dict, list)):
                    return nested
            for nested in value.values():
                result = find(nested)
                if result is not None:
                    return result
        elif isinstance(value, list):
            for nested in value:
                result = find(nested)
                if result is not None:
                    return result
        return None

    value = find(record)
    return decimal_value(value) if value is not None else None


def category_name(value):
    """Keep the category label supplied with the product, including nested API shapes."""
    if isinstance(value, dict):
        value = first_value(value, "title", "name", "label", "categoryName", default="")
    elif isinstance(value, list):
        value = ", ".join(str(category_name(item)) for item in value if item)
    return str(value or "").strip()[:160]


def sync_catalog(client=None, *, run=None):
    run = run or SyncRun.objects.create(status="running")
    def report(percent, stage):
        SyncRun.objects.filter(pk=run.pk).update(progress=percent, stage=stage)
    warnings = []
    generation = None
    committed = False
    try:
        with catalog_sync_lock():
            client = client or ChortkeClient()
            report(5, "دریافت کالاها از چرتکه")
            products = client.get_products()
            report(15, "آماده‌سازی تصاویر کالاها")
            divisor = Decimal(str(settings.CHORTKE_PRICE_DIVISOR))
            if divisor <= 0:
                raise ValueError("CHORTKE_PRICE_DIVISOR باید بزرگ‌تر از صفر باشد.")
            records = []
            sources = {}
            skipped = 0
            for item in products:
                code = str(first_value(item, "code", "accountingCode", "id", default="")).strip()
                if not code:
                    skipped += 1
                    continue
                image_source = first_value(item, "imageUrl", "image_url", "photoUrl", "pictureUrl", default="")
                if isinstance(image_source, dict):
                    image_source = first_value(image_source, "url", "src", default="")
                source = urljoin(client.base_url + "/", image_source)[:1000] if isinstance(image_source, str) and image_source else ""
                sources[code] = source
                records.append((code, item))
            generation, optimized, image_errors = prepare_images(sources, client=client, progress=lambda done, total: report(15 + int(45 * done / max(1, total)), f"دریافت و فشرده‌سازی تصویر {done} از {total}"))
            names = {code: str(first_value(item, "title", "name", default=code)) for code, item in records}
            for error in image_errors:
                error["name"] = names.get(error["code"], "")
            run.image_errors = image_errors
            report(65, "ذخیره کالاها در دیتابیس")
            with transaction.atomic():
                # Clearing every prior reference prevents removed products retaining old images.
                Product.objects.update(is_active=False, image_url="", image_source_url="", image_size=0)
                for code, item in records:
                    stock = stock_value(item)
                    defaults = {
                        "accounting_code": str(first_value(item, "accountingCode", default="")),
                        "barcode": str(first_value(item, "barcode", default="")),
                        "name": str(first_value(item, "title", "name", default=code))[:255],
                        "category": category_name(first_value(item, "category", "categoryName", default="")),
                        "description": str(first_value(item, "salesDescription", "description", default="")),
                        "unit": str(first_value(item, "unit", default=""))[:32],
                        "sale_price": decimal_value(first_value(item, "sellPrice", "salePrice", "price"), divisor=divisor),
                        "is_active": first_value(item, "active", "isActive", default=True) is not False,
                        "image_url": "", "image_source_url": sources[code], "image_size": 0,
                    }
                    if stock is not None:
                        defaults["stock"] = stock
                    defaults.update(optimized.get(code, {}))
                    Product.objects.update_or_create(chortke_code=code, defaults=defaults)
            committed = True
            try:
                prune_images(generation)
            except OSError:
                warnings.append("بعضی فایل‌های قبلی تصویر قابل حذف نبودند؛ دسترسی پوشه رسانه را بررسی کنید.")
            if image_errors:
                warnings.append(f"تصویر {len(image_errors)} کالا آماده نشد؛ تصویر قبلی آن‌ها حذف شده است.")
            try:
                report(80, "بروزرسانی جست‌وجوی هوشمند")
                rebuild_index(progress=lambda done, total: report(80 + int(18 * done / max(1, total)), f"بردارسازی {done} از {total}"))
            except Exception:
                warnings.append("بردارسازی تکمیل نشد؛ جست‌وجوی املایی فعال است. دستور rebuild_product_search را دوباره اجرا کنید.")
            cache.clear()
            if skipped:
                warnings.append(f"{skipped} کالا به‌دلیل نداشتن شناسه یکتا رد شد.")
            run.received_count = len(products)
            run.saved_count = len(records)
            run.skipped_count = skipped
            run.status = "warning" if warnings else "success"
            run.message = "\n".join(warnings)
    except Exception as exc:
        if generation and not committed:
            remove_managed(image_root() / generation)
        run.status = "failed"
        run.message = str(exc)
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "message", "finished_at"])
        raise
    run.finished_at = timezone.now()
    run.progress = 100
    run.stage = "همگام‌سازی تکمیل شد"
    run.save(update_fields=["status", "message", "received_count", "saved_count", "skipped_count", "finished_at", "progress", "stage", "image_errors"])
    return run
