"""Public discovery URLs are generated from the current catalog snapshot."""
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse
from django.utils.encoding import iri_to_uri
from django.views.decorators.http import require_safe

from store.catalog.models import Product


def absolute_url(path):
    return settings.SITE_ORIGIN.rstrip("/") + iri_to_uri(path)


def canonical(request):
    path = request.path
    if path == reverse("storefront:catalog"):
        # Keep distinct catalog/category pages while dropping tracking parameters.
        params = {key: request.GET[key] for key in ("category", "q", "sort", "page") if request.GET.get(key)}
        if params.get("page") == "1":
            params.pop("page")
        if params:
            path += "?" + urlencode(params)
    return {"canonical_url": absolute_url(path)}


@require_safe
def robots(request):
    private = ("admin", "panel", "accounts", "checkout", "orders", "support", "api", "smart-wholesale-bot")
    lines = ["User-agent: *", "Allow: /"] + [f"Disallow: /{path}/" for path in private]
    lines += ["", "Sitemap: " + absolute_url(reverse("sitemap")), ""]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


@require_safe
def sitemap(request):
    namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
    ET.register_namespace("", namespace)
    root = ET.Element(f"{{{namespace}}}urlset")

    def add(path, modified=None):
        node = ET.SubElement(root, f"{{{namespace}}}url")
        ET.SubElement(node, f"{{{namespace}}}loc").text = absolute_url(path)
        if modified:
            ET.SubElement(node, f"{{{namespace}}}lastmod").text = modified.isoformat()

    add(reverse("storefront:home"))
    add(reverse("storefront:catalog"))
    # Hidden products have no public detail page and must not be advertised.
    products = Product.objects.filter(is_active=True, is_visible=True)
    categories = products.exclude(category="").order_by("category").values_list("category", flat=True).distinct()
    for category in categories:
        add(reverse("storefront:catalog") + "?" + urlencode({"category": category}))
    for product_id, modified in products.order_by("pk").values_list("pk", "synced_at").iterator():
        add(reverse("storefront:product-detail", args=[product_id]), modified)
    # Deliberately no persistent cache: syncs and visibility changes apply immediately.
    return HttpResponse(ET.tostring(root, encoding="utf-8", xml_declaration=True),
                        content_type="application/xml; charset=utf-8",
                        headers={"Cache-Control": "no-cache"})
