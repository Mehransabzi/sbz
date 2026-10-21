import hashlib
from django.conf import settings
from django.utils import timezone
from store.catalog.models import Product, ProductEmbedding
from .embeddings import vectors
from .normalization import document_text, normalize


def fingerprint(product):
    return hashlib.sha256(document_text(product).encode()).hexdigest()


def rebuild_index(*, force=False, progress=None):
    products = list(Product.objects.filter(is_active=True).order_by("pk"))
    existing = {row.product_id: row for row in ProductEmbedding.objects.all()}
    changed = [p for p in products if force or p.pk not in existing or existing[p.pk].content_hash != fingerprint(p) or existing[p.pk].model_name != settings.SEARCH_EMBEDDING_MODEL]
    count = 0
    for offset in range(0, len(changed), 32):
        batch = changed[offset:offset+32]
        embedded = vectors([normalize(document_text(p)) for p in batch])
        for product, vector in zip(batch, embedded):
            ProductEmbedding.objects.update_or_create(product=product, defaults={"content_hash": fingerprint(product), "model_name": settings.SEARCH_EMBEDDING_MODEL, "vector": vector, "updated_at": timezone.now()})
            count += 1
        if progress:
            progress(count, len(changed))
    ProductEmbedding.objects.filter(product__is_active=False).delete()
    return count
