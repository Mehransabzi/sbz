from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from .models import User


@admin.register(User)
class CustomerUserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "phone", "is_approved", "debt", "is_staff", "created_at")
    list_filter = ("is_approved", "is_staff", "is_active", "created_at")
    search_fields = ("username", "phone", "first_name", "last_name")
    ordering = ("-created_at",)
    list_editable = ("is_approved",)
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("اطلاعات مشتری", {"fields": ("first_name", "last_name", "phone", "address", "debt", "debt_updated_at", "is_approved")}),
        ("دسترسی", {"fields": ("is_active", "is_staff", "is_superuser", "user_permissions")}),
        ("تاریخ‌ها", {"fields": ("last_login", "date_joined", "created_at")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("username", "first_name", "last_name", "phone", "password1", "password2", "is_staff", "is_superuser")}),)
    filter_horizontal = ("user_permissions",)
    readonly_fields = ("last_login", "date_joined", "created_at")


if admin.site.is_registered(Group):
    admin.site.unregister(Group)
