import hashlib
import math
import time
import requests
from django.conf import settings
from django.core.cache import cache
from store.ai.client import post_gapgpt
from store.controlpanel.models import SiteConfiguration


def vectors(texts, *, query=False):
    key = SiteConfiguration.current().get_ai_api_key()
    if not key:
        raise RuntimeError("کلید GapGPT در تنظیمات سایت ثبت نشده است.")
    payload = {"model": settings.SEARCH_EMBEDDING_MODEL, "input": texts}
    if "text-embedding-3" in settings.SEARCH_EMBEDDING_MODEL:
        payload["dimensions"] = settings.SEARCH_EMBEDDING_DIMENSIONS
    for attempt in range(3 if not query else 1):
        try:
            response = post_gapgpt("/embeddings", headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, json=payload, timeout=(8, 15) if query else (8, 45))
            response.raise_for_status()
            break
        except requests.RequestException as exc:
            status = exc.response.status_code if exc.response is not None else None
            transient = isinstance(exc, (requests.Timeout, requests.ConnectionError)) or status in {429, 500, 502, 503, 504}
            if query or not transient or attempt == 2:
                raise
            if exc.response is not None:
                exc.response.close()
            time.sleep(2 ** attempt)
    rows = sorted(response.json().get("data", []), key=lambda row: row["index"])
    if len(rows) != len(texts):
        raise ValueError("پاسخ سرویس بردارسازی کامل نبود.")
    result = []
    for index, row in enumerate(rows):
        vector = row.get("embedding")
        if row.get("index") != index or not isinstance(vector, list) or not vector or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vector):
            raise ValueError("پاسخ برداری معتبر دریافت نشد.")
        result.append(vector)
    return result


def query_vector(text):
    key = "catalog-query-vector:" + hashlib.sha256((settings.SEARCH_EMBEDDING_MODEL + " ".join(sorted(text.split()))).encode()).hexdigest()
    result = cache.get(key)
    if result is None:
        if cache.get("catalog-embedding-unavailable"):
            return []
        try:
            result = vectors([text], query=True)[0]
        except Exception:
            cache.set("catalog-embedding-unavailable", True, 60)
            raise
        cache.set(key, result, 1800)
    return result


def cosine(a, b):
    if not a or len(a) != len(b):
        return 0.0
    denominator = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    return sum(x*y for x, y in zip(a, b)) / denominator if denominator else 0.0
