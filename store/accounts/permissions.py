def can_view_prices(user):
    return bool(user and user.is_authenticated and (user.is_staff or user.is_approved))
