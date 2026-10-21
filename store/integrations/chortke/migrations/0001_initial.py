from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="SyncRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("running", "در حال اجرا"), ("success", "موفق"), ("warning", "موفق با هشدار"), ("failed", "ناموفق")], default="running", max_length=16)),
                ("received_count", models.PositiveIntegerField(default=0)),
                ("saved_count", models.PositiveIntegerField(default=0)),
                ("skipped_count", models.PositiveIntegerField(default=0)),
                ("message", models.TextField(blank=True)),
            ],
            options={"verbose_name": "نوبت همگام‌سازی چرتکه", "verbose_name_plural": "گزارش‌های همگام‌سازی چرتکه", "ordering": ["-started_at"]},
        ),
    ]
