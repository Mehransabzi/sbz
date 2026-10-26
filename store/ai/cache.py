from django.core.cache import cache


AI_CUSTOMER_GENERATION_KEY = "sbz:ai:customer-response-generation"
AI_ADMIN_GENERATION_KEY = "sbz:ai:admin-response-generation"
AI_CATALOG_GENERATION_KEY = "sbz:ai:catalog-response-generation"


def generation(key):
    try:
        return cache.get(key, 1)
    except Exception:
        return 0


def bump(key):
    try:
        return cache.incr(key)
    except ValueError:
        try:
            cache.set(key, 2, None)
            return 2
        except Exception:
            return 0
    except Exception:
        return 0


def invalidate_catalog_answers():
    """Version out product answers after a catalog sync without clearing other caches."""
    return bump(AI_CATALOG_GENERATION_KEY)


def clear_ai_response_caches():
    """Invalidate AI completions and the short-lived admin site summary only."""
    bump(AI_CUSTOMER_GENERATION_KEY)
    bump(AI_ADMIN_GENERATION_KEY)
    bump(AI_CATALOG_GENERATION_KEY)
    try:
        cache.delete("gapgpt-admin-site-summary-v2")
    except Exception:
        pass
