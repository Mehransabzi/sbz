from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "chortke_code", "product_name", "quantity", "unit_price", "line_total")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "customer_name", "company_name", "phone", "total", "status", "created_at")
    list_filter = ("status", "province", "created_at")
    search_fields = ("order_number", "customer_name", "company_name", "phone")
    readonly_fields = ("order_number", "created_at", "total")
    inlines = (OrderItemInline,)
