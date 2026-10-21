from django.core.management.base import BaseCommand
from store.catalog.search.indexing import rebuild_index


class Command(BaseCommand):
    help = "Generate and persist changed product embeddings using the site's GapGPT key."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        count = rebuild_index(force=options["force"], progress=lambda done, total: self.stdout.write(f"Indexed {done}/{total}", ending="\n"))
        self.stdout.write(self.style.SUCCESS(f"Indexed {count} changed products."))
