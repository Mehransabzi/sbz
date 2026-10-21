import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "local-only-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "rest_framework",
    "store.catalog.apps.CatalogConfig",
    "store.accounts.apps.AccountsConfig",
    "store.storefront.apps.StorefrontConfig",
    "store.integrations.chortke.apps.ChortkeIntegrationConfig",
    "store.orders.apps.OrdersConfig",
    "store.ai.apps.AiConfig",
    "store.support.apps.SupportConfig",
    "store.controlpanel.apps.ControlPanelConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "store.accounts.context_processors.customer_access",
                "store.storefront.context_processors.shop_contact",
            ],
        },
    },
]
AUTH_USER_MODEL = "customer_accounts.User"
AUTHENTICATION_BACKENDS = ["store.accounts.backends.SingleUserModelBackend"]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fa-ir"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
}

CHORTKE_API_BASE_URL = os.getenv("CHORTKE_API_BASE_URL", "https://api.chortke.app").rstrip("/")
CHORTKE_ACCESS_TOKEN = os.getenv("CHORTKE_ACCESS_TOKEN", "")
CHORTKE_PRICE_DIVISOR = float(os.getenv("CHORTKE_PRICE_DIVISOR", "1"))
CHORTKE_PAGE_SIZE = max(1, min(int(os.getenv("CHORTKE_PAGE_SIZE", "100")), 500))

GAPGPT_API_BASE_URL = "https://api.gapgpt.app/v1"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "shopsite-ai-cache", "TIMEOUT": 600}}


# Product vectors are persisted locally; embeddings use the configured GapGPT key.
SEARCH_EMBEDDING_MODEL = os.getenv("SEARCH_EMBEDDING_MODEL", "text-embedding-3-small")
SEARCH_SEMANTIC_ENABLED = os.getenv("SEARCH_SEMANTIC_ENABLED", "true").lower() == "true"
SEARCH_EMBEDDING_DIMENSIONS = 384
PRODUCT_IMAGE_MAX_SIZE = 960
PRODUCT_IMAGE_WEBP_QUALITY = 76
PRODUCT_IMAGE_DOWNLOAD_LIMIT = 12 * 1024 * 1024
