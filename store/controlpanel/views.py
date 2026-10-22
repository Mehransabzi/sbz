from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Max, Value, IntegerField
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from django.contrib.auth import get_user_model
from store.catalog.models import Product
from store.catalog.search.engine import search_products
from store.integrations.chortke.models import SyncRun
from store.integrations.chortke.services import sync_catalog
from store.orders.models import Order, OrderItem
from store.ai.models import ChatConversation, CustomerImageUsage
from store.ai.usage import usage_day
from .forms import AnnouncementForm, SiteConfigurationForm, CustomerDebtForm
from django.utils import timezone
from .models import Announcement, SiteConfiguration

Customer = get_user_model()

staff_required = user_passes_test(lambda user: user.is_authenticated and user.is_staff, login_url="accounts:login")


def page(request, rows):
    return Paginator(rows, 25).get_page(request.GET.get("page"))


@staff_required
@require_http_methods(["GET", "HEAD", "POST"])
def announcements(request, announcement_id=None):
    announcement = get_object_or_404(Announcement, pk=announcement_id) if announcement_id else None
    form = AnnouncementForm(request.POST if request.method == "POST" else None, instance=announcement)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "اطلاعیه ذخیره شد.")
        return redirect("controlpanel:announcements")
    return render(request, "controlpanel/announcements.html", {
        "form": form, "editing": announcement,
        "page_obj": page(request, Announcement.objects.all()),
    })


@staff_required
@require_POST
def delete_announcement(request, announcement_id):
    get_object_or_404(Announcement, pk=announcement_id).delete()
    messages.success(request, "اطلاعیه حذف شد.")
    return redirect("controlpanel:announcements")


@staff_required
def dashboard(request):
    context = {
        "product_count": Product.objects.filter(is_active=True).count(),
        "customer_count": Customer.objects.filter(is_staff=False).count(),
        "pending_customers": Customer.objects.filter(is_staff=False, is_approved=False).count(),
        "pending_orders": Order.objects.filter(status="pending_confirmation").count(),
        "recent_orders": Order.objects.all()[:8],
        "sync_runs": SyncRun.objects.all()[:5],
    }
    return render(request, "controlpanel/dashboard.html", context)


def customer_usage_rows():
    return Customer.objects.filter(is_staff=False).annotate(
        image_total=Coalesce(Sum("image_usage__count"), Value(0), output_field=IntegerField()),
        image_today=Coalesce(Sum("image_usage__count", filter=Q(image_usage__day=usage_day())), Value(0), output_field=IntegerField()),
        last_image_at=Max("image_usage__updated_at"),
    ).order_by("-created_at", "-pk")


@staff_required
def image_usage_report(request):
    query = request.GET.get("q", "").strip()[:100]
    sort = request.GET.get("sort", "total")
    rows = customer_usage_rows()
    if query:
        rows = rows.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(phone__icontains=query) | Q(username__icontains=query))
    rows = rows.order_by("-image_today" if sort == "today" else "-image_total", "-created_at")
    totals = CustomerImageUsage.objects.filter(user__is_staff=False).aggregate(total=Sum("count"), today=Sum("count", filter=Q(day=usage_day())))
    return render(request, "controlpanel/image_usage.html", {"page_obj": page(request, rows), "query": query, "sort": sort, "total_uploads": totals["total"] or 0, "today_uploads": totals["today"] or 0, "usage_date": usage_day()})


@staff_required
def customers(request):
    query = request.GET.get("q", "").strip()[:100]
    rows = customer_usage_rows()
    if query:
        rows = rows.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(username__icontains=query) | Q(phone__icontains=query))
    return render(request, "controlpanel/customers.html", {"page_obj": page(request, rows), "query": query})


@staff_required
def products(request):
    query = request.GET.get("q", "").strip()[:120]
    visibility = request.GET.get("visibility", "all")
    rows = Product.objects.all()
    if visibility == "hidden":
        rows = rows.filter(is_visible=False)
    elif visibility == "visible":
        rows = rows.filter(is_visible=True)
    if query:
        rows = search_products(query, queryset=rows)
    counts = {
        "all_count": Product.objects.count(),
        "visible_count": Product.objects.filter(is_visible=True).count(),
        "hidden_count": Product.objects.filter(is_visible=False).count(),
    }
    return render(request, "controlpanel/products.html", {"page_obj": page(request, rows), "query": query, "visibility": visibility, **counts})


@staff_required
def orders(request):
    query = request.GET.get("q", "").strip()[:100]
    search_by = request.GET.get("by", "all")
    status = request.GET.get("status", "")
    rows = Order.objects.all()
    if query:
        if search_by == "name":
            rows = rows.filter(customer_name__icontains=query)
        elif search_by == "phone":
            rows = rows.filter(phone__icontains=query)
        elif search_by == "invoice":
            rows = rows.filter(order_number__icontains=query)
        else:
            search_by = "all"
            rows = rows.filter(Q(order_number__icontains=query) | Q(customer_name__icontains=query) | Q(phone__icontains=query))
    if status in {key for key, _ in Order.STATUS_CHOICES}:
        rows = rows.filter(status=status)
    sort_fields = {"name": ("customer_name", "-created_at"), "phone": ("phone", "-created_at"), "invoice": ("order_number",)}
    rows = rows.order_by(*sort_fields.get(search_by, ("-created_at",)))
    return render(request, "controlpanel/orders.html", {"page_obj": page(request, rows), "query": query, "search_by": search_by, "status_filter": status, "statuses": Order.STATUS_CHOICES})


@staff_required
def order_invoice(request, order_id):
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=order_id)
    from store.accounts.views import _invoice_pdf_response
    return _invoice_pdf_response(order, request)


@staff_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    return render(request, "controlpanel/order_detail.html", {"order": order, "items": OrderItem.objects.filter(order=order).select_related("product"), "statuses": Order.STATUS_CHOICES})


@staff_required
@require_POST
def customer_approval(request, profile_id):
    profile = get_object_or_404(Customer, pk=profile_id, is_staff=False)
    profile.is_approved = request.POST.get("approved") == "1"
    profile.save(update_fields=["is_approved"])
    messages.success(request, "وضعیت دسترسی مشتری ذخیره شد.")
    return redirect("controlpanel:customers")


@staff_required
@require_POST
def order_status(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    status = request.POST.get("status")
    if status in {key for key, _ in Order.STATUS_CHOICES}:
        order.status = status
        order.save(update_fields=["status"])
        messages.success(request, "وضعیت سفارش تغییر کرد.")
    else:
        messages.error(request, "وضعیت انتخاب‌شده معتبر نیست.")
    return redirect("controlpanel:orders")


@staff_required
@require_POST
def sync(request):
    import subprocess, sys
    from django.conf import settings
    from django.http import JsonResponse
    from django.db import transaction
    from datetime import timedelta
    with transaction.atomic():
        # Serialise panel starts on the singleton configuration row.
        SiteConfiguration.current()
        SiteConfiguration.objects.filter(pk=1).update(updated_at=timezone.now())
        cutoff = timezone.now() - timedelta(minutes=30)
        SyncRun.objects.filter(status="running", started_at__lt=cutoff).update(status="failed", message="کار قبلی متوقف شده است؛ دوباره تلاش کنید.", finished_at=timezone.now())
        run = SyncRun.objects.filter(status="running").first()
        if run is None:
            run = SyncRun.objects.create(status="running", stage="شروع همگام‌سازی")
            def launch_worker(run_id=run.pk):
                try:
                    subprocess.Popen([sys.executable, str(settings.BASE_DIR / "manage.py"), "run_catalog_sync", str(run_id)], cwd=settings.BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                except Exception:
                    SyncRun.objects.filter(pk=run_id).update(status="failed", message="فرایند همگام‌سازی شروع نشد؛ دسترسی اجرای پایتون را بررسی کنید.", finished_at=timezone.now())
            transaction.on_commit(launch_worker)
    if request.headers.get("Accept") == "application/json":
        return JsonResponse({"id": run.pk, "status_url": reverse("controlpanel:sync-status", args=[run.pk])})
    return redirect("controlpanel:sync-report")


@staff_required
def sync_status(request, run_id):
    from django.http import JsonResponse
    run = get_object_or_404(SyncRun, pk=run_id)
    response = JsonResponse({"id": run.pk, "status": run.status, "progress": run.progress, "stage": run.stage, "message": run.message, "image_errors": run.image_errors, "saved_count": run.saved_count})
    response["Cache-Control"] = "no-store"
    return response


@staff_required
def sync_report(request):
    return render(request, "controlpanel/sync_report.html", {"runs": SyncRun.objects.all()[:20]})


@staff_required
def site_settings(request):
    config = SiteConfiguration.current()
    form = SiteConfigurationForm(request.POST or None, request.FILES or None, instance=config)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تنظیمات فروشگاه ذخیره شد.")
        return redirect("controlpanel:site-settings")
    return render(request, "controlpanel/site_settings.html", {"form": form, "site_config": config, "ai_key_configured": bool(config.ai_api_key_encrypted)})


@staff_required
@require_POST
def toggle_product_visibility(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    product.is_visible = not product.is_visible
    product.save(update_fields=["is_visible"])
    state = "نمایش داده می‌شود" if product.is_visible else "از سایت پنهان شد"
    messages.success(request, f"{product.name} اکنون {state}.")
    return redirect(request.POST.get("next") or "controlpanel:products")


@staff_required
def customer_debt(request, profile_id):
    profile = get_object_or_404(Customer, pk=profile_id, is_staff=False)
    form = CustomerDebtForm(request.POST if request.method == "POST" else None, initial={"debt": profile.debt})
    if request.method == "POST" and form.is_valid():
        profile.debt = form.cleaned_data["debt"]
        profile.debt_updated_at = timezone.now()
        profile.save(update_fields=["debt", "debt_updated_at"])
        messages.success(request, "مانده بدهی مشتری ذخیره شد.")
        return redirect("controlpanel:customers")
    return render(request, "controlpanel/customer_debt.html", {"form": form, "customer": profile})


@staff_required
def ai_analysis(request):
    conversations = ChatConversation.objects.filter(messages__isnull=False).select_related("user").distinct().order_by("-updated_at")[:100]
    return render(request, "controlpanel/ai_analysis.html", {"site_config": SiteConfiguration.current(), "conversations": conversations, "conversation_context": request.GET.get("conversation", "")})


@staff_required
def customer_ai_chats(request):
    rows = ChatConversation.objects.filter(messages__isnull=False).select_related("user").distinct().order_by("-updated_at")
    selected = None
    selected_id = request.GET.get("conversation")
    if selected_id:
        selected = get_object_or_404(ChatConversation.objects.select_related("user"), pk=selected_id)
    page_obj = page(request, rows)
    chat_messages = list(selected.messages.order_by("-created_at", "-pk").values("role", "content", "created_at")[:80]) if selected else []
    chat_messages.reverse()
    return render(request, "controlpanel/ai_customer_chats.html", {"page_obj": page_obj, "selected": selected, "chat_messages": chat_messages})


@staff_required
@require_POST
def delete_customer_ai_chat(request, conversation_id):
    conversation = get_object_or_404(ChatConversation, pk=conversation_id)
    conversation.delete()
    messages.success(request, "گفت‌وگوی مشتری و پیام‌های آن حذف شد.")
    return redirect("controlpanel:ai-customer-chats")


@staff_required
@require_POST
def delete_all_customer_chats(request):
    if request.POST.get("confirmation") == "DELETE":
        count = ChatConversation.objects.count()
        ChatConversation.objects.all().delete()
        from django.core.cache import cache
        cache.clear()
        messages.success(request, f"{count} گفتگو و پیام‌هایشان حذف شدند. آمار مصرف تصاویر حفظ شد.")
    return redirect("controlpanel:ai-customer-chats")


@staff_required
def product_description(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    if request.method == "POST":
        if request.POST.get("action") == "generate":
            from .content_services import generate_description
            from django.http import JsonResponse
            try:
                draft = generate_description(product)
                request.session["product-description-sources:"+str(product.pk)] = draft["sources"]
                return JsonResponse(draft)
            except Exception:
                return JsonResponse({"error": "ساخت توضیحات فعلاً انجام نشد. کلید و اتصال سرویس را بررسی کنید."}, status=503)
        text = request.POST.get("description", "").strip()
        if len(text) > 6000:
            messages.error(request, "توضیحات حداکثر ۶۰۰۰ حرف باشد.")
        else:
            product.description_override = text
            product.description_sources = request.session.get("product-description-sources:"+str(product.pk), product.description_sources)
            product.save(update_fields=["description_override", "description_sources", "synced_at"])
            from django.core.cache import cache
            cache.clear()
            messages.success(request, "توضیحات ذخیره شد.")
            return redirect("controlpanel:products")
    return render(request, "controlpanel/product_description.html", {"product": product})


@staff_required
def daily_stories(request):
    from .models import DailyStorySelection
    from .content_services import daily_story_products
    return render(request, "controlpanel/daily_stories.html", {"products": daily_story_products(), "shop": SiteConfiguration.current(), "today": timezone.localdate()})


@staff_required
def product_image(request, product_id):
    from django.core.cache import cache
    from django.db import transaction
    from .forms import ProductImageForm

    product = get_object_or_404(Product, pk=product_id)
    form = ProductImageForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            product = Product.objects.select_for_update().get(pk=product_id)
            old_name = product.custom_image.name
            storage = product.custom_image.storage
            product.custom_image = form.cleaned_data["image"]
            product.save(update_fields=["custom_image"])
            if old_name and old_name != product.custom_image.name and old_name.startswith("product-images/custom/"):
                transaction.on_commit(lambda name=old_name: storage.delete(name))
            transaction.on_commit(cache.clear)
        messages.success(request, "عکس با فرمت WebP ذخیره شد. در صورت نبود عکس چرتکه، عکس شما نمایش داده می‌شود.")
        return redirect("controlpanel:product-image", product_id=product.pk)
    return render(request, "controlpanel/product_image.html", {"product": product, "form": form})
