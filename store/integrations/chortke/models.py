from django.db import models


class SyncRun(models.Model):
    STATUS_CHOICES = [
        ("running", "در حال اجرا"),
        ("success", "موفق"),
        ("warning", "موفق با هشدار"),
        ("failed", "ناموفق"),
    ]

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="running")
    received_count = models.PositiveIntegerField(default=0)
    saved_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)
    progress = models.PositiveSmallIntegerField(default=0)
    stage = models.CharField(max_length=160, blank=True)
    image_errors = models.JSONField(default=list)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "نوبت همگام‌سازی چرتکه"
        verbose_name_plural = "گزارش‌های همگام‌سازی چرتکه"

    def __str__(self):
        return f"{self.started_at:%Y-%m-%d %H:%M} · {self.get_status_display()}"
