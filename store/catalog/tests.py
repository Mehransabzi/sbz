import io
import tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from .models import Product, ProductEmbedding
from .search.engine import search_products
from .search.indexing import rebuild_index, fingerprint
from .search.normalization import normalize
from .images import encode_webp, prepare_images, prune_images, remove_managed


class SearchTests(TestCase):
    def setUp(self):
        cache.clear()
        self.oil = Product.objects.create(chortke_code="A123", name="فیلتر روغن پژو ۲۰۶", description="تصفیه روغن موتور")
        self.brake = Product.objects.create(chortke_code="B456", name="لنت ترمز پژو ۴۰۵")
        self.hidden = Product.objects.create(chortke_code="X123", name="فیلتر روغن مخفی", is_visible=False)

    def test_normalization(self):
        self.assertEqual(normalize("كيت ١٢۳ ي"), "کیت 123 ی")

    def test_transposition_and_word_order(self):
        self.assertEqual(search_products("رونغ فیلتر پژو 206").first(), self.oil)
        self.assertEqual(search_products("فیلتر رغون").first(), self.oil)

    def test_short_transposed_letters(self):
        self.assertEqual(search_products("نلت ترمز").first(), self.brake)

    def test_api_search_and_price_gate(self):
        from store.accounts.models import User
        response = self.client.get("/api/catalog/products/", {"q": "فیلتر رغون"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], self.oil.chortke_code)
        self.assertIsNone(response.json()[0]["price"])
        user = User.objects.create_user(username="09121234567", is_approved=True)
        self.client.force_login(user)
        response = self.client.get("/api/catalog/products/", {"q": "A123"})
        self.assertEqual(response.json()[0]["price"], 0.0)

    def test_typo(self):
        self.assertEqual(search_products("فیلتر روغم").first(), self.oil)

    def test_code_and_visibility(self):
        self.assertEqual(search_products("A123").first(), self.oil)
        self.assertNotIn(self.hidden, search_products("فیلتر روغن"))
        self.assertFalse(search_products("X123").exists())

    def test_semantic_match(self):
        ProductEmbedding.objects.create(product=self.oil, content_hash=fingerprint(self.oil), model_name=settings.SEARCH_EMBEDDING_MODEL, vector=[1, 0])
        with patch("store.catalog.search.engine.query_vector", return_value=[1, 0]):
            self.assertEqual(search_products("پاکسازی چربی موتور").first(), self.oil)

    def test_provider_failure_keeps_fuzzy_search(self):
        ProductEmbedding.objects.create(product=self.oil, content_hash=fingerprint(self.oil), model_name=settings.SEARCH_EMBEDDING_MODEL, vector=[1, 0])
        with patch("store.catalog.search.engine.query_vector", side_effect=RuntimeError()):
            self.assertEqual(search_products("فیلتر رغون").first(), self.oil)

    def test_index_only_changed_text(self):
        with patch("store.catalog.search.indexing.vectors", side_effect=lambda docs: [[1, 0] for _ in docs]) as provider:
            self.assertEqual(rebuild_index(), 3)
            self.assertEqual(rebuild_index(), 0)
            self.oil.sale_price = 123
            self.oil.save()
            self.assertEqual(rebuild_index(), 0)
            self.oil.description = "new description"
            self.oil.save()
            self.assertEqual(rebuild_index(), 1)
            self.assertEqual(provider.call_count, 2)


class ImageTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.tmp.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        output = io.BytesIO()
        Image.new("RGBA", (1600, 1200), (80, 100, 200, 150)).save(output, "PNG")
        self.raw = output.getvalue()

    def test_compression_dimensions_transparency(self):
        output = encode_webp(self.raw)
        with Image.open(io.BytesIO(output)) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertLessEqual(max(image.size), 960)
            self.assertIn("A", image.getbands())
        self.assertLess(len(output), len(self.raw))

    def test_generation_cleanup_protects_other_media(self):
        root = Path(self.tmp.name)
        (root / "logo.png").write_bytes(b"logo")
        with patch("store.catalog.images.download_image", return_value=self.raw):
            old, _, _ = prepare_images({"1": "https://example.com/old.png"})
            new, rows, errors = prepare_images({"1": "https://example.com/new.png"})
        self.assertFalse(errors)
        prune_images(new)
        self.assertFalse((root / "product-images" / old).exists())
        self.assertTrue((root / "product-images" / new).exists())
        self.assertTrue((root / "logo.png").exists())
        self.assertTrue(rows["1"]["image_url"].endswith(".webp"))
        with self.assertRaises(ValueError):
            remove_managed(root / "logo.png")

    def test_sync_failure_preserves_previous_images(self):
        from store.integrations.chortke.services import sync_catalog
        from types import SimpleNamespace
        old, rows, _ = prepare_images({})
        old_file = Path(self.tmp.name) / "product-images" / old / "old.webp"
        old_file.write_bytes(b"old")
        product = Product.objects.create(chortke_code="1", name="old", image_url="/media/product-images/"+old+"/old.webp")
        client = SimpleNamespace(base_url="https://example.com", access_token="", get_products=lambda: [{"code": "1", "title": "new", "price": "invalid"}])
        with self.assertRaises(ValueError):
            sync_catalog(client)
        product.refresh_from_db()
        self.assertIn(old, product.image_url)
        self.assertTrue(old_file.exists())

    def test_sync_clears_omitted_images_and_prunes(self):
        from store.integrations.chortke.services import sync_catalog
        from types import SimpleNamespace
        old, _, _ = prepare_images({})
        old_file = Path(self.tmp.name) / "product-images" / old / "old.webp"
        old_file.write_bytes(b"old")
        product = Product.objects.create(chortke_code="1", name="old", image_url="/media/product-images/"+old+"/old.webp")
        client = SimpleNamespace(base_url="https://example.com", access_token="", get_products=lambda: [{"code": "1", "title": "new", "price": 123}])
        with patch("store.integrations.chortke.services.rebuild_index", return_value=0):
            sync_catalog(client)
        product.refresh_from_db()
        self.assertEqual(product.image_url, "")
        self.assertFalse(old_file.exists())
