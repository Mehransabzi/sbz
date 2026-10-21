from django.urls import path

from . import views
from store.ai.views import customer_chat_page

app_name = "storefront"

urlpatterns = [
    path("", views.home, name="home"),
    path("catalog/", views.catalog, name="catalog"),
    path("smart-wholesale-bot/", customer_chat_page, name="smart-bot"),
    path("products/<int:product_id>/", views.product_detail, name="product-detail"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/submit/", views.submit_order, name="submit-order"),
    path("orders/<str:order_number>/", views.order_success, name="order-success"),
]
