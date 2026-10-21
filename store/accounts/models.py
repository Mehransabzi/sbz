from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    groups = None
    REQUIRED_FIELDS = []
    phone = models.CharField(max_length=24, blank=True, default="", db_index=True, verbose_name="شماره موبایل")
    address = models.TextField(max_length=800, blank=True, default="", verbose_name="نشانی")
    debt = models.DecimalField(max_digits=18, decimal_places=0, null=True, blank=True, validators=[MinValueValidator(0)], verbose_name="مانده بدهی (ریال)")
    debt_updated_at = models.DateTimeField(null=True, blank=True)
    is_approved = models.BooleanField(default=False, db_index=True, verbose_name="تأیید دسترسی به قیمت‌ها")
    created_at = models.DateTimeField(default=timezone.now, editable=False, verbose_name="تاریخ ثبت‌نام")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "کاربر / مشتری"
        verbose_name_plural = "کاربران و مشتریان"

    @property
    def customer_profile(self):
        """Compatibility alias: customer details now live on this user row."""
        return self

    def __str__(self):
        return self.get_full_name() or self.phone or self.username
