from django.conf import settings
from django.db import models


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending_confirmation", "در انتظار تأیید فروشگاه"),
        ("confirmed", "تأیید شده"),
        ("shipped", "ارسال شده"),
        ("cancelled", "لغو شده"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    order_number = models.CharField(max_length=40, unique=True)
    customer_name = models.CharField(max_length=120)
    company_name = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=24)
    province = models.CharField(max_length=80, blank=True, default="")
    city = models.CharField(max_length=80, blank=True, default="")
    address = models.TextField(max_length=800, blank=True, default="")
    note = models.TextField(max_length=1000, blank=True)
    total = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="pending_confirmation", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "سفارش"
        verbose_name_plural = "سفارش‌ها"

    def __str__(self):
        return f"{self.order_number} · {self.customer_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.SET_NULL)
    chortke_code = models.CharField(max_length=100)
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    line_total = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        verbose_name = "ردیف سفارش"
        verbose_name_plural = "ردیف‌های سفارش"

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"
