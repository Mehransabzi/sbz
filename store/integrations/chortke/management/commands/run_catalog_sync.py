from django.core.management.base import BaseCommand
from store.integrations.chortke.models import SyncRun
from store.integrations.chortke.services import sync_catalog

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("run_id", type=int)
    def handle(self, *args, **options):
        sync_catalog(run=SyncRun.objects.get(pk=options["run_id"]))
