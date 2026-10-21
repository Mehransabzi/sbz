from django.core.management.base import BaseCommand, CommandError

from store.integrations.chortke.client import ChortkeError
from store.integrations.chortke.services import sync_catalog


class Command(BaseCommand):
    help = "Import Chortke products, prices, and image URLs; sync stock when the response includes it."

    def handle(self, *args, **options):
        try:
            run = sync_catalog()
        except (ChortkeError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"همگام‌سازی {run.get_status_display()}: دریافت {run.received_count}، "
                f"ذخیره {run.saved_count}، ردشده {run.skipped_count}."
            )
        )
        if run.message:
            self.stdout.write(self.style.WARNING(run.message))
