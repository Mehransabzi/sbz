import io
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import requests
from PIL import Image
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from store.accounts.models import User
from store.catalog.images import prepare_images
from store.catalog.models import Product, ProductEmbedding
from store.catalog.search.engine import search_products
from .models import SyncRun
from .services import sync_catalog


@override_settings(SEARCH_SEMANTIC_ENABLED=False)
class CatalogSyncTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.media = override_settings(MEDIA_ROOT=self.tmp.name)
        self.media.enable()
        self.addCleanup(self.media.disable)
        self.embedding = patch('store.catalog.search.indexing.vectors', side_effect=lambda docs: [[1, 0] for _ in docs])
        self.embedding.start()
        self.addCleanup(self.embedding.stop)
        cache.clear()

    def sync(self, items):
        client = SimpleNamespace(base_url='https://example.com', access_token='', get_products=lambda: items)
        return sync_catalog(client)

    def test_distinct_ids_sharing_a_code_are_not_overwritten(self):
        old = Product.objects.create(chortke_code='670', accounting_code='1347', name='نسخه قبلی', description_override='متن مدیر', is_visible=False)
        archived = Product.objects.create(chortke_code='removed', name='حذف‌شده از چرتکه')
        items = [{'id': 100, 'code': '670', 'accountingCode': '0670', 'title': 'کالای اول', 'sellPrice': 100},
                 {'id': 200, 'code': '670', 'accountingCode': '1347', 'title': 'کالای دوم', 'sellPrice': 200}]
        run = self.sync(items)
        old.refresh_from_db()
        archived.refresh_from_db()
        first = Product.objects.get(chortke_id='100')
        self.assertEqual(old.chortke_id, '200')
        self.assertEqual(old.chortke_code, '670')
        self.assertEqual(old.description_override, 'متن مدیر')
        self.assertFalse(old.is_visible)
        self.assertFalse(archived.is_active)
        self.assertNotEqual(first.pk, old.pk)
        self.assertNotEqual(first.chortke_code, old.chortke_code)
        self.assertEqual(first.accounting_code, '0670')
        self.assertEqual(first.sale_price, 100)
        self.assertEqual(run.status, 'success')
        self.assertEqual((run.received_count, run.saved_count), (2, 2))
        self.assertEqual(run.catalog_summary['active'], 2)
        self.assertEqual(run.catalog_summary['public'], 1)
        self.assertEqual(run.catalog_summary['inactive'], 1)
        self.assertEqual(run.catalog_summary['shared_codes'][0]['count'], 2)
        rerun = self.sync(list(reversed(items)))
        self.assertEqual(Product.objects.count(), 3)
        self.assertEqual(Product.objects.get(chortke_id='100').pk, first.pk)
        self.assertEqual(Product.objects.get(chortke_id='200').pk, old.pk)
        self.assertEqual(rerun.catalog_summary['created'], 0)
        old.is_visible = True
        old.save(update_fields=['is_visible'])
        user = User.objects.create_user(username='sync-buyer', is_approved=True)
        self.client.force_login(user)
        cart = self.client.get(reverse('cart-products'), {'code': [old.chortke_code, first.chortke_code]}).json()['products']
        self.assertEqual(len(cart), 2)
        self.assertEqual({p['price'] for p in cart}, {'100.00', '200.00'})

    def test_changed_code_keeps_id_cart_key_and_product_page(self):
        self.sync([{'id': 1, 'code': 'old', 'title': 'نام قدیم'}])
        product = Product.objects.get(chortke_id='1')
        self.sync([{'id': 1, 'code': 'new', 'title': 'نام جدید'}])
        product.refresh_from_db()
        self.assertEqual(product.chortke_code, 'old')
        self.assertEqual(product.source_code, 'new')
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(search_products('new').get(), product)

    def test_repeated_identical_id_is_counted_once_and_conflict_fails(self):
        item = {'id': 1, 'code': 'x', 'title': 'کالا'}
        run = self.sync([item, dict(item)])
        self.assertEqual(run.status, 'success')
        self.assertEqual((run.received_count, run.saved_count), (2, 1))
        self.assertEqual(run.catalog_summary['repeated_rows'], 1)
        with self.assertRaises(ValueError):
            self.sync([item, {**item, 'title': 'شناسه متناقض'}])
        self.assertEqual(Product.objects.get().name, 'کالا')
        self.assertTrue(Product.objects.get().is_active)

    def test_fresh_product_is_searchable_after_sync_in_same_process(self):
        self.sync([{'id': 1, 'code': 'old', 'title': 'لنت ترمز قدیمی'}])
        self.assertFalse(search_products('کلید شیشه بالابر جدید').exists())
        run = self.sync([{'id': 1, 'code': 'old', 'title': 'لنت ترمز قدیمی'},
                         {'id': 2, 'code': 'fresh', 'title': 'کلید شیشه بالابر جدید'}])
        fresh = Product.objects.get(chortke_id='2')
        self.assertIn(fresh, search_products('کلید شیشه بالابر جدید'))
        self.assertEqual(search_products('fresh').get(), fresh)
        self.assertContains(self.client.get('/catalog/', {'q': 'fresh'}), fresh.name)
        self.assertEqual(run.search_index['indexed'], 2)
        self.assertEqual(run.search_index['missing'], 0)

    def test_failed_image_preserves_previous_file_in_new_generation(self):
        raw = io.BytesIO()
        Image.new('RGB', (32, 32), 'green').save(raw, 'PNG')
        with patch('store.catalog.images.download_image', return_value=raw.getvalue()):
            old_generation, rows, _ = prepare_images({'x': 'https://example.com/old.png'})
        product = Product.objects.create(chortke_code='x', name='کالا', **rows['x'])
        response = requests.Response()
        response.status_code = 404
        error = requests.HTTPError(response=response)
        with patch('store.catalog.images.download_image', side_effect=error) as download:
            run = self.sync([{'id': 1, 'code': 'x', 'title': 'کالا', 'imageUrl': '/missing.png'}])
        product.refresh_from_db()
        self.assertEqual(download.call_count, 1)
        self.assertEqual(run.status, 'success')
        self.assertEqual(run.image_errors, [])
        self.assertEqual(run.image_fallbacks[0]['fallback'], 'previous')
        self.assertEqual(run.image_fallbacks[0]['reason'], 'HTTP 404')
        self.assertNotIn(old_generation, product.image_url)
        self.assertTrue((Path(self.tmp.name) / product.image_url.removeprefix('/media/')).is_file())
        self.assertFalse((Path(self.tmp.name) / 'product-images' / old_generation).exists())

    def test_placeholder_is_explicit_and_503_retries(self):
        response = requests.Response()
        response.status_code = 503
        error = requests.HTTPError(response=response)
        with patch('store.catalog.images.download_image', side_effect=error) as download, patch('store.catalog.images.time.sleep'):
            run = self.sync([{'id': 1, 'code': 'x', 'title': 'کالا', 'imageUrl': '/unavailable.png'}])
        self.assertEqual(download.call_count, 3)
        self.assertEqual(run.status, 'success')
        self.assertEqual(run.image_fallbacks[0]['attempts'], 3)
        self.assertEqual(run.image_fallbacks[0]['fallback'], 'placeholder')
        self.assertIn('product-placeholder.svg', Product.objects.get().display_image_url)

    def test_search_failure_is_not_reported_as_success(self):
        with patch('store.catalog.search.indexing.vectors', side_effect=RuntimeError('private proxy details')):
            run = self.sync([{'id': 1, 'code': 'x', 'title': 'کالا'}])
        self.assertEqual(run.status, 'warning')
        self.assertEqual(run.search_index['status'], 'failed')
        self.assertEqual(run.search_index['missing'], 1)
        self.assertEqual(run.search_index['error'], 'RuntimeError')
        self.assertNotIn('private', str(run.search_index))
        call_command('rebuild_product_search', sync_run=run.pk, stdout=io.StringIO())
        run.refresh_from_db()
        self.assertEqual(run.search_index['source'], 'rebuild_product_search')
        self.assertEqual(run.search_index['status'], 'success')
        self.assertEqual(run.search_index['indexed'], 1)

    def test_panel_public_count_matches_catalog_and_inactive_is_separate(self):
        self.sync([{'id': 1, 'code': 'a', 'title': 'فعال'}, {'id': 2, 'code': 'b', 'title': 'غیرفعال', 'active': 'false'}])
        user = User.objects.create_user(username='sync-manager', is_staff=True)
        self.client.force_login(user)
        response = self.client.get(reverse('controlpanel:products'))
        self.assertEqual(response.context['visibility'], 'visible')
        self.assertEqual(response.context['inventory']['active'], 1)
        self.assertEqual(response.context['inventory']['public'], self.client.get('/catalog/').context['page_obj'].paginator.count)
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertEqual(self.client.get(reverse('controlpanel:products'), {'visibility': 'inactive'}).context['page_obj'].paginator.count, 1)
        self.assertContains(self.client.get(reverse('controlpanel:sync-report')), 'وضعیت فعلی جستجو')
