from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db import transaction
from store.catalog.models import Product
from store.catalog.images import catalog_sync_lock, prepare_images, prune_images, remove_managed, image_root, preserve_previous_image


class Command(BaseCommand):
    help = "Replace existing remote product images with a fresh compressed WebP generation."

    def handle(self, *args, **options):
        with catalog_sync_lock():
            products = list(Product.objects.all())
            sources = {p.chortke_code: p.image_source_url or (p.image_url if p.image_url.startswith(("https://", "http://")) else "") for p in products}
            generation, optimized, errors = prepare_images(sources)
            try:
                for product in products:
                    if any(error["code"] == product.chortke_code for error in errors):
                        optimized[product.chortke_code] = preserve_previous_image(product, generation)
                with transaction.atomic():
                    for product in products:
                        data = optimized.get(product.chortke_code, {})
                        product.image_url = data.get("image_url", "")
                        product.image_source_url = sources[product.chortke_code]
                        product.image_size = data.get("image_size", 0)
                    Product.objects.bulk_update(products, ["image_url", "image_source_url", "image_size"])
            except Exception:
                remove_managed(image_root() / generation)
                raise
            prune_images(generation)
            cache.clear()
            self.stdout.write(f"WebP images: {len(optimized)}; failed: {len(errors)}; bytes: {sum(row['image_size'] for row in optimized.values())}")
