from django.core.management.base import BaseCommand, CommandError
from store.catalog.images import catalog_sync_lock
from store.catalog.search.indexing import rebuild_index, index_status, index_error
from store.integrations.chortke.models import SyncRun


class Command(BaseCommand):
    help = "Generate and persist changed product embeddings using the site's GapGPT key."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--sync-run", type=int, help="Record the result against this synchronization report.")

    def handle(self, *args, **options):
        run = None
        if options["sync_run"]:
            try:
                run = SyncRun.objects.get(pk=options["sync_run"])
            except SyncRun.DoesNotExist as exc:
                raise CommandError("Sync report does not exist.") from exc
        with catalog_sync_lock():
            try:
                count = rebuild_index(force=options["force"], progress=lambda done, total: self.stdout.write(f"Indexed {done}/{total}", ending="\n"))
                result = index_status()
                result.update(changed=count, source="rebuild_product_search")
                if result["missing"]:
                    raise ValueError("Some active products are not indexed.")
            except Exception as exc:
                result = index_status()
                result.update(status="failed", error=index_error(exc), source="rebuild_product_search")
                if run:
                    SyncRun.objects.filter(pk=run.pk).update(search_index=result)
                raise CommandError(f"Search rebuild failed ({index_error(exc)}).") from None
            if run:
                SyncRun.objects.filter(pk=run.pk).update(search_index=result)
            self.stdout.write(self.style.SUCCESS(f"Indexed {count} changed products; coverage {result['indexed']}/{result['total']}."))
