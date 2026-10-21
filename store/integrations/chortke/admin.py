from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import path, reverse

from .models import SyncRun
from .services import sync_catalog


@admin.register(SyncRun)
class SyncRunAdmin(admin.ModelAdmin):
    change_list_template = "admin/chortke_integration/syncrun/change_list.html"
    list_display = ("started_at", "finished_at", "status", "received_count", "saved_count", "skipped_count")
    list_filter = ("status",)
    readonly_fields = tuple(field.name for field in SyncRun._meta.fields)

    def get_urls(self):
        custom_urls = [
            path(
                "sync-products/",
                self.admin_site.admin_view(self.sync_products),
                name=f"{self.model._meta.app_label}_{self.model._meta.model_name}_sync_products",
            )
        ]
        return custom_urls + super().get_urls()

    def sync_products(self, request):
        if request.method != "POST":
            raise PermissionDenied
        try:
            run = sync_catalog()
        except Exception as exc:
            self.message_user(request, f"همگام‌سازی انجام نشد: {exc}", level=messages.ERROR)
        else:
            level = messages.WARNING if run.status == "warning" else messages.SUCCESS
            self.message_user(
                request,
                f"همگام‌سازی {run.get_status_display()}؛ {run.saved_count} کالا ذخیره شد. {run.message}",
                level=level,
            )
        return redirect(reverse("admin:chortke_integration_syncrun_changelist"))
