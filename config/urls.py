from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.http import HttpResponse
from pathlib import Path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from store.storefront import seo

admin.site.site_header = "مدیریت فروشگاه سبزی"
admin.site.site_title = "پنل مدیریت"
admin.site.index_title = "مدیریت فروشگاه و مشتریان"


@api_view(["GET"])
@permission_classes([AllowAny])
def health(_request):
    return Response({"status": "ok", "service": "shopsite-api"})


def service_worker(_request):
    worker = Path(settings.BASE_DIR) / "store" / "storefront" / "static" / "storefront" / "service-worker.js"
    return HttpResponse(worker.read_text(encoding="utf-8"), content_type="application/javascript; charset=utf-8",
                        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})


urlpatterns = [
    path("robots.txt", seo.robots, name="robots"),
    path("sitemap.xml", seo.sitemap, name="sitemap"),
    path("service-worker.js", service_worker, name="service-worker"),
    path("support/", include("store.support.urls")),
    path("panel/", include("store.controlpanel.urls")),
    path("admin/", admin.site.urls),
    path("accounts/", include("store.accounts.urls")),
    path("", include("store.storefront.urls")),
    path("api/health/", health),
    path("api/catalog/", include("store.catalog.urls")),
    path("api/integrations/chortke/", include("store.integrations.chortke.urls")),
    path("api/ai/", include("store.ai.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
