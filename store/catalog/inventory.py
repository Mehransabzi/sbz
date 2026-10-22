from django.db.models import Count, Q
from .models import Product


def catalog_counts():
    return Product.objects.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(is_active=True)),
        public=Count("pk", filter=Q(is_active=True, is_visible=True)),
        hidden=Count("pk", filter=Q(is_active=True, is_visible=False)),
        inactive=Count("pk", filter=Q(is_active=False)),
    )
