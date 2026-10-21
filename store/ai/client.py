"""HTTP helpers for requests sent to the GapGPT API."""

import requests
from django.conf import settings


def post_gapgpt(path, **kwargs):
    """POST to GapGPT, optionally through the host-provided HTTP proxy."""
    base_url = settings.GAPGPT_API_BASE_URL.rstrip("/")
    endpoint = path if path.startswith("/") else "/" + path
    proxy_url = getattr(settings, "GAPGPT_PROXY_URL", "").strip()
    request_options = {}
    if proxy_url:
        request_options["proxies"] = {"http": proxy_url, "https": proxy_url}
    return requests.post(base_url + endpoint, **request_options, **kwargs)
