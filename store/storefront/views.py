import json
import secrets
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_safe, require_POST

from store.accounts.decorators import approved_customer_required
from store.accounts.permissions import can_view_prices
from store.catalog.models import Product
from store.catalog.search.engine import search_products
from store.controlpanel.models import SiteConfiguration
from store.integrations.chortke.models import SyncRun
from store.orders.forms import OrderForm
from store.orders.models import Order, OrderItem


def _category_options():
    raw_categories = (
        Product.objects.filter(is_active=True, is_visible=True)
        .exclude(category="")
        .order_by("category")
        .values_list("category", flat=True)
        .distinct()
    )
    return [(value, value.rsplit(">", 1)[-1].strip()) for value in raw_categories]


def _catalog_context(request, *, page_size=24):
    products = Product.objects.filter(is_active=True, is_visible=True)
    query = request.GET.get("q", "").strip()[:120]
    category = request.GET.get("category", "").strip()
    sort = request.GET.get("sort", "featured")
    if sort in {"price_asc", "price_desc"} and not can_view_prices(request.user):
        sort = "featured"

    if category:
        products = products.filter(category__iexact=category)
    if query:
        products = search_products(query, queryset=products)
    ordering = {
        "price_asc": ("sale_price", "name"),
        "price_desc": ("-sale_price", "name"),
        "name": ("name",),
    }.get(sort, ("-synced_at", "name"))
    if not query or sort != "featured":
        products = products.order_by(*ordering)

    paginator = Paginator(products, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    last_sync = SyncRun.objects.first()
    return {
        "products": page_obj.object_list,
        "page_obj": page_obj,
        "query": query,
        "active_category": category,
        "sort": sort,
        "categories": _category_options(),
        "last_sync": last_sync,
    }


@require_safe
def home(request):
    return render(request, "storefront/home.html", {"categories": _category_options(), "site_config": SiteConfiguration.objects.first()})


@require_safe
def catalog(request):
    return render(request, "storefront/catalog.html", _catalog_context(request))


@require_safe
def product_detail(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_active=True, is_visible=True)
    return render(request, "storefront/product_detail.html", {"product": product})


@approved_customer_required
@require_safe
def checkout(request):
    return render(request, "storefront/checkout.html", {"form": OrderForm()})


@approved_customer_required
@require_POST
def submit_order(request):
    form = OrderForm(request.POST)
    if not form.is_valid():
        return render(request, "storefront/checkout.html", {"form": form}, status=400)

    try:
        submitted_items = json.loads(form.cleaned_data["cart_items"])
    except (TypeError, json.JSONDecodeError):
        return HttpResponseBadRequest("سبد خرید معتبر نیست.")
    if not isinstance(submitted_items, list) or not submitted_items or len(submitted_items) > 50:
        messages.error(request, "سبد خرید خالی یا نامعتبر است.")
        return redirect("storefront:checkout")

    quantities = {}
    for item in submitted_items:
        if not isinstance(item, dict):
            messages.error(request, "اطلاعات سبد خرید معتبر نیست.")
            return redirect("storefront:checkout")
        code = str(item.get("code", "")).strip()[:100]
        quantity = item.get("quantity")
        if not code or type(quantity) is not int or not 1 <= quantity <= 999:
            messages.error(request, "کالا یا تعداد ثبت‌شده معتبر نیست.")
            return redirect("storefront:checkout")
        quantities[code] = quantities.get(code, 0) + quantity
        if quantities[code] > 999:
            messages.error(request, "حداکثر تعداد هر کالا در هر سفارش ۹۹۹ عدد است.")
            return redirect("storefront:checkout")

    with transaction.atomic():
        locked_products = {
            product.chortke_code: product
            for product in Product.objects.select_for_update().filter(
                chortke_code__in=quantities, is_active=True, is_visible=True
            )
        }
        if len(locked_products) != len(quantities):
            messages.error(request, "یک یا چند کالا دیگر در فهرست فروش نیستند. سبد خرید را تازه‌سازی کنید.")
            return redirect("storefront:checkout")
        total = sum(
            (product.sale_price * quantities[code] for code, product in locked_products.items()),
            start=Decimal("0"),
        )
        order_number = f"SBZ-{secrets.token_hex(16).upper()}"
        profile = getattr(request.user, "customer_profile", None)
        order = Order.objects.create(
            user=request.user,
            order_number=order_number,
            customer_name=request.user.get_full_name().strip() or request.user.username,
            company_name="",
            phone=profile.phone if profile else request.user.username,
            province="",
            city="",
            address=profile.address if profile else "",
            note=form.cleaned_data["note"],
            total=total,
        )
        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    product=product,
                    chortke_code=code,
                    product_name=product.name,
                    quantity=quantities[code],
                    unit_price=product.sale_price,
                    line_total=product.sale_price * quantities[code],
                )
                for code, product in locked_products.items()
            ]
        )

    return redirect("storefront:order-success", order_number=order.order_number)


@approved_customer_required
@require_safe
def order_success(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    # Order numbers are hard to guess and this receipt is intentionally read-only.
    return render(request, "storefront/order_success.html", {"order": order})
