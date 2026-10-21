from django.core.paginator import Paginator
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_http_methods

from store.orders.models import Order
from .forms import MobileAuthenticationForm, RegistrationForm


class CustomerLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = MobileAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or reverse("accounts:profile")


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("accounts:profile")
    return render(request, "accounts/register.html", {"form": form})


class CustomerLogoutView(LogoutView):
    next_page = "storefront:home"


class CustomerPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:password-change-done")


@login_required
def password_change_done(request):
    return render(request, "accounts/password_change_done.html")


@login_required
def profile(request):
    orders = Order.objects.filter(user=request.user).prefetch_related("items")
    paginator = Paginator(orders, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "accounts/profile.html", {"orders": page_obj.object_list, "order_count": paginator.count, "page_obj": page_obj})


@login_required
def profile_order(request, order_number):
    order = get_object_or_404(
        Order.objects.prefetch_related("items"),
        user=request.user,
        order_number=order_number,
    )
    return render(request, "accounts/profile_order.html", {"order": order, "items": order.items.all()})


def _invoice_pdf_response(order, request):
    import base64
    from pathlib import Path
    from django.conf import settings
    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from store.controlpanel.models import SiteConfiguration
    font = Path(settings.BASE_DIR) / "store/storefront/static/storefront/fonts/Vazirmatn-wght.woff2"
    html = render_to_string("accounts/invoice.html", {
        "order": order, "items": order.items.all(),
        "shop": SiteConfiguration.objects.first() or SiteConfiguration(),
        "font_data": base64.b64encode(font.read_bytes()).decode("ascii"),
    }, request=request)
    from weasyprint import HTML
    pdf = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="invoice-{order.pk}.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_http_methods(["GET"])
def invoice_download(request, order_number):
    order = get_object_or_404(Order.objects.prefetch_related("items"), user=request.user, order_number=order_number)
    return _invoice_pdf_response(order, request)


