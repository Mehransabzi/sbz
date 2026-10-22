import hashlib
from django.core.cache import cache
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from store.catalog.models import Product, ProductEmbedding
from .embeddings import vectors
from .normalization import document_text, normalize


def fingerprint(product):
    return hashlib.sha256(document_text(product).encode()).hexdigest()


def is_current(product, row):
    return bool(row and row.vector and row.content_hash == fingerprint(product)
                and row.model_name == settings.SEARCH_EMBEDDING_MODEL)


def index_status():
    products = list(Product.objects.filter(is_active=True))
    rows = {row.product_id: row for row in ProductEmbedding.objects.filter(product__is_active=True)}
    indexed = sum(is_current(product, rows.get(product.pk)) for product in products)
    return {"status": "success" if indexed == len(products) else "incomplete",
            "total": len(products), "indexed": indexed, "missing": len(products) - indexed,
            "model": settings.SEARCH_EMBEDDING_MODEL,
            "semantic_enabled": getattr(settings, "SEARCH_SEMANTIC_ENABLED", True),
            "checked_at": timezone.now().isoformat()}


def index_error(exc):
    # Exception strings may contain proxy credentials or request headers.
    response = getattr(exc, "response", None)
    return f"HTTP {response.status_code}" if response is not None else type(exc).__name__


def rebuild_index(*, force=False, progress=None):
    products = list(Product.objects.filter(is_active=True).order_by("pk"))
    existing = {row.product_id: row for row in ProductEmbedding.objects.all()}
    changed = [p for p in products if force or not is_current(p, existing.get(p.pk))]
    count = 0
    for offset in range(0, len(changed), 32):
        batch = changed[offset:offset+32]
        embedded = vectors([normalize(document_text(p)) for p in batch])
        if len(embedded) != len(batch) or any(not vector for vector in embedded):
            raise ValueError("پاسخ بردارسازی برای همه کالاهای این دسته کامل نبود.")
        with transaction.atomic():
            for product, vector in zip(batch, embedded):
                ProductEmbedding.objects.update_or_create(product=product, defaults={"content_hash": fingerprint(product), "model_name": settings.SEARCH_EMBEDDING_MODEL, "vector": vector, "updated_at": timezone.now()})
                count += 1
        if progress:
            progress(count, len(changed))
    ProductEmbedding.objects.filter(product__is_active=False).delete()
    cache.clear()
    return count
