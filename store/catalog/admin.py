from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "chortke_code", "sale_price", "is_active", "synced_at")
    list_filter = ("is_active", "category")
    search_fields = ("name", "chortke_code", "accounting_code", "barcode")
    readonly_fields = ("synced_at",)
    exclude = ("stock",)
