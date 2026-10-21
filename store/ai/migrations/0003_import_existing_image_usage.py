from django.db import migrations


def import_existing_usage(apps, schema_editor):
    from zoneinfo import ZoneInfo
    from django.utils import timezone
    from collections import defaultdict
    Message = apps.get_model("ai_assistant", "ChatMessage")
    Usage = apps.get_model("ai_assistant", "CustomerImageUsage")
    records = defaultdict(lambda: {"count": 0, "updated_at": None})
    for user_id, sent_at in Message.objects.filter(role="user", content="تصویر فاکتور/فهرست خرید ارسال شد.").values_list("conversation__user_id", "created_at").iterator():
        key = (user_id, timezone.localtime(sent_at, ZoneInfo("Asia/Tehran")).date())
        records[key]["count"] += 1
        records[key]["updated_at"] = max(records[key]["updated_at"] or sent_at, sent_at)
    for (user_id, day), values in records.items():
        row, created = Usage.objects.get_or_create(user_id=user_id, day=day, defaults=values)
        if not created and values["count"] > row.count:
            row.count = values["count"]
            row.updated_at = max(row.updated_at, values["updated_at"])
            row.save(update_fields=["count", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [("ai_assistant", "0002_customerimageusage")]
    operations = [migrations.RunPython(import_existing_usage, migrations.RunPython.noop)]
