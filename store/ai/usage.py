from zoneinfo import ZoneInfo
from django.db.models import F, Sum
from django.utils import timezone
from .models import CustomerImageUsage

DAILY_IMAGE_LIMIT = 5


def usage_day():
    return timezone.localdate(timezone=ZoneInfo("Asia/Tehran"))


def image_usage(user, day=None):
    day = day or usage_day()
    used = CustomerImageUsage.objects.filter(user=user, day=day).values_list("count", flat=True).first() or 0
    total = CustomerImageUsage.objects.filter(user=user).aggregate(value=Sum("count"))["value"] or 0
    return {"limit": DAILY_IMAGE_LIMIT, "used": used, "remaining": max(0, DAILY_IMAGE_LIMIT-used), "total": total, "day": day.isoformat()}


def reserve_image_upload(user):
    # Conditional SQL update enforces the cap even for concurrent requests.
    day = usage_day()
    row, _ = CustomerImageUsage.objects.get_or_create(user=user, day=day)
    accepted = CustomerImageUsage.objects.filter(pk=row.pk, count__lt=DAILY_IMAGE_LIMIT).update(count=F("count")+1, updated_at=timezone.now())
    return bool(accepted), image_usage(user, day)
