from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect

from .permissions import can_view_prices


def approved_customer_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url="accounts:login")
        if not can_view_prices(request.user):
            messages.info(request, "حساب شما پس از بررسی فروشگاه تأیید می‌شود؛ تا آن زمان قیمت‌ها نمایش داده نمی‌شوند.")
            return redirect("storefront:home")
        return view(request, *args, **kwargs)

    return wrapped
