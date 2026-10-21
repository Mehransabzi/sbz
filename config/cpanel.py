"""Production settings for the packaged sbzpart.ir cPanel application."""
import os
from .settings import *  # noqa: F403
from django.core.exceptions import ImproperlyConfigured

DEBUG = False
SEARCH_SEMANTIC_ENABLED = os.getenv("SEARCH_SEMANTIC_ENABLED", "false").lower() == "true"
if len(SECRET_KEY) < 50:  # noqa: F405
    raise ImproperlyConfigured("Set the production DJANGO_SECRET_KEY from the release .env file.")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "sbzpart.ir,www.sbzpart.ir").split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "https://sbzpart.ir,https://www.sbzpart.ir").split(",")
    if origin.strip()
]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
# Let cPanel enforce HTTPS at the web server. This avoids redirect loops on
# hosting providers that terminate TLS before Passenger.
SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "false").lower() == "true"
# Enable only when the hosting provider confirms it strips/replaces this header.
if os.getenv("DJANGO_TRUST_PROXY_SSL_HEADER", "false").lower() == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0"))
DATABASES["default"]["OPTIONS"] = {"timeout": 30}  # noqa: F405
