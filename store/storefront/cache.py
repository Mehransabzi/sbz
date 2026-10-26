from django.core.cache import cache


CATALOG_GENERATION_KEY = "sbz:storefront:catalog-generation"


def catalog_cache_version():
    try:
        generation = cache.get(CATALOG_GENERATION_KEY, 1)
    except Exception:
        generation = 0
    try:
        from django.db.models import Count, Max
        from store.catalog.models import Product

        state = Product.objects.aggregate(count=Count("pk"), latest=Max("synced_at"))
        latest = state["latest"].isoformat() if state["latest"] else "none"
        return f"{generation}:{state['count']}:{latest}"
    except Exception:
        return generation


def bump_catalog_cache_version():
    """Invalidate cached public catalog fragments across Passenger workers."""
    try:
        return cache.incr(CATALOG_GENERATION_KEY)
    except ValueError:
        try:
            cache.set(CATALOG_GENERATION_KEY, 2, None)
            return 2
        except Exception:
            return 0
    except Exception:
        return 0
