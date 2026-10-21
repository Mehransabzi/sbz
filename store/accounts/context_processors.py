from .permissions import can_view_prices


def customer_access(request):
    return {"can_view_prices": can_view_prices(request.user)}
