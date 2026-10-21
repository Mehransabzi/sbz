from django.urls import path

from .views import ProductListView, cart_products

urlpatterns = [path("cart-products/", cart_products, name="cart-products"), path("products/", ProductListView.as_view(), name="catalog-products")]
