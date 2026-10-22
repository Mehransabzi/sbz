from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

from django.core.cache import cache

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from store.catalog.models import Product
from store.catalog.images import catalog_sync_lock, prepare_images, prune_images, remove_managed, image_root, preserve_previous_image
from store.catalog.inventory import catalog_counts
from store.catalog.search.indexing import rebuild_index, index_status, index_error

from .client import ChortkeClient
from .models import SyncRun
from .identity import product_plan


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


def active_value(item):
    value = first_value(item, "active", "isActive", default=True)
    if value is True or value == 1 or str(value).strip().lower() in {"true", "yes", "1"}:
        return True
    if value is False or value == 0 or str(value).strip().lower() in {"false", "no", "0"}:
        return False
    raise ValueError("وضعیت فعال‌بودن کالا در پاسخ چرتکه معتبر نیست.")


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
            previous = list(Product.objects.all())
            records, skipped, repeated_rows, shared_codes = product_plan(products, previous, first_value)
            if not records and any(p.is_active for p in previous):
                raise ValueError("پاسخ چرتکه هیچ کالای معتبری ندارد؛ کالاهای فعلی برای جلوگیری از حذف ناخواسته حفظ شدند.")
            sources = {}
            for record in records:
                code, item = record["key"], record["item"]
                image_source = first_value(item, "imageUrl", "image_url", "photoUrl", "pictureUrl", default="")
                if isinstance(image_source, dict):
                    image_source = first_value(image_source, "url", "src", default="")
                source = urljoin(client.base_url + "/", image_source)[:1000] if isinstance(image_source, str) and image_source else ""
                sources[code] = source
            generation, optimized, image_errors = prepare_images(sources, client=client, progress=lambda done, total: report(15 + int(45 * done / max(1, total)), f"دریافت و فشرده‌سازی تصویر {done} از {total}"))
            by_key = {record["key"]: record for record in records}
            run.image_fallbacks = []
            for error in image_errors:
                record = by_key[error["code"]]
                error["name"] = str(first_value(record["item"], "title", "name", default=error["code"]))[:255]
                error["source_code"] = record["source_code"]
                error["accounting_code"] = record["accounting_code"]
                old = record["previous"]
                fallback = "placeholder"
                try:
                    retained = preserve_previous_image(old, generation)
                    if retained:
                        optimized[record["key"]] = retained
                        fallback = "previous"
                    elif old and old.custom_image and old.custom_image.storage.exists(old.custom_image.name):
                        fallback = "custom"
                except (OSError, ValueError):
                    error["previous_unavailable"] = True
                run.image_fallbacks.append({**error, "fallback": fallback})
            # Handled image failures stay visible as fallback details, not unresolved errors.
            run.image_errors = []
            report(65, "ذخیره کالاها در دیتابیس")
            with transaction.atomic():
                # Clearing every prior reference prevents removed products retaining old images.
                Product.objects.update(is_active=False, image_url="", image_source_url="", image_size=0)
                for record in records:
                    code, item = record["key"], record["item"]
                    stock = stock_value(item)
                    defaults = {
                        "chortke_id": record["source_id"],
                        "source_code": record["source_code"],
                        "accounting_code": str(first_value(item, "accountingCode", default="")),
                        "barcode": str(first_value(item, "barcode", default="")),
                        "name": str(first_value(item, "title", "name", default=code))[:255],
                        "category": category_name(first_value(item, "category", "categoryName", default="")),
                        "description": str(first_value(item, "salesDescription", "description", default="")),
                        "unit": str(first_value(item, "unit", default=""))[:32],
                        "sale_price": decimal_value(first_value(item, "sellPrice", "salePrice", "price"), divisor=divisor),
                        "is_active": active_value(item),
                        "image_url": "", "image_source_url": sources[code], "image_size": 0,
                    }
                    if stock is not None:
                        defaults["stock"] = stock
                    defaults.update(optimized.get(code, {}))
                    Product.objects.update_or_create(chortke_code=code, defaults=defaults)
            committed = True
            counts = catalog_counts()
            matched = {record["previous"].pk for record in records if record["previous"]}
            removed = [p.chortke_code for p in previous if p.pk not in matched]
            run.catalog_summary = {**counts, "unique_received": len(records), "repeated_rows": repeated_rows,
                                   "shared_codes": shared_codes, "absent_codes": removed,
                                   "upstream_inactive": sum(not active_value(r["item"]) for r in records),
                                   "created": sum(r["previous"] is None for r in records)}
            try:
                prune_images(generation)
            except OSError:
                warnings.append("بعضی فایل‌های قبلی تصویر قابل حذف نبودند؛ دسترسی پوشه رسانه را بررسی کنید.")
            try:
                report(80, "بروزرسانی جست‌وجوی هوشمند")
                changed = rebuild_index(progress=lambda done, total: report(80 + int(18 * done / max(1, total)), f"بردارسازی {done} از {total}"))
                run.search_index = {**index_status(), "changed": changed, "source": "sync"}
                if run.search_index["missing"]:
                    raise ValueError("فهرست بردارهای کالاهای فعال کامل نیست.")
            except Exception as exc:
                run.search_index = {**index_status(), "status": "failed", "error": index_error(exc), "source": "sync"}
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
    run.save(update_fields=["status", "message", "received_count", "saved_count", "skipped_count", "finished_at", "progress", "stage", "image_errors", "image_fallbacks", "catalog_summary", "search_index"])
    return run
