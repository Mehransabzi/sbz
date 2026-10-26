from django.test import TestCase
from django.core.cache import cache
from django.urls import reverse
from store.accounts.models import User
from store.catalog.models import Product
from store.orders.models import Order, OrderItem


class CustomerInterfaceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="09120000000", first_name="مشتری", last_name="نمونه", phone="09120000000", address="نشانی نمونه", is_approved=True, debt=123000)
        self.product = Product.objects.create(chortke_code="C1", name="لنت نمونه", sale_price=250000, image_url="/media/product-images/g-test/sample.webp")

    def test_current_cart_metadata_requires_approval(self):
        url = reverse("cart-products")
        self.assertEqual(self.client.get(url, {"code": "C1"}).status_code, 403)
        self.client.force_login(self.user)
        self.user.is_approved = False
        self.user.save()
        self.assertEqual(self.client.get(url, {"code": "C1"}).status_code, 403)

    def test_cart_metadata_images_prices_and_hidden_products(self):
        hidden = Product.objects.create(chortke_code="C2", name="پنهان", is_visible=False)
        self.client.force_login(self.user)
        response = self.client.get(reverse("cart-products"), {"code": ["C1", hidden.chortke_code]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(len(response.json()['products']), 1)
        self.assertEqual(response.json()['products'][0]['image'], self.product.image_url)
        self.assertEqual(response.json()['products'][0]['price'], '250000.00')

    def test_metadata_limit(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("cart-products"), {"code": [str(i) for i in range(101)]}).status_code, 400)

    def test_profile_order_privacy_and_table_markup(self):
        own = Order.objects.create(user=self.user, order_number="OWN-01", customer_name="نمونه", phone=self.user.phone, total=250000)
        other = User.objects.create_user(username="09129999999")
        Order.objects.create(user=other, order_number="PRIVATE-OTHER", customer_name="دیگر", phone=other.username, total=1)
        OrderItem.objects.create(order=own, product=self.product, chortke_code="C1", product_name=self.product.name, quantity=1, unit_price=250000, line_total=250000)
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, 'data-view-switch="orders"')
        self.assertContains(response, self.user.address)
        self.assertContains(response, 'OWN-01')
        self.assertNotContains(response, 'PRIVATE-OTHER')
        self.assertEqual(self.client.get(reverse("accounts:profile-order", args=['OWN-01'])).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:profile-order", args=['PRIVATE-OTHER'])).status_code, 404)

    def test_catalog_and_checkout_templates(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("storefront:catalog"))
        self.assertContains(response, 'data-view-switch="catalog"')
        self.assertContains(response, 'catalog-table')
        self.assertContains(response, 'data-image="'+self.product.image_url+'"')
        response = self.client.get(reverse("storefront:checkout"))
        self.assertContains(response, 'checkout-item-count')
        self.assertContains(response, 'cart-refresh-state')

    def test_catalog_price_fragment_is_separated_by_approval(self):
        guest_client = self.client
        guest = guest_client.get(reverse("storefront:catalog"))
        self.assertNotContains(guest, "۲۵۰٬۰۰۰")

        guest_client.force_login(self.user)
        approved = guest_client.get(reverse("storefront:catalog"))
        self.assertContains(approved, "۲۵۰٬۰۰۰")

        self.user.is_approved = False
        self.user.save(update_fields=["is_approved"])
        pending = guest_client.get(reverse("storefront:catalog"))
        self.assertNotContains(pending, "۲۵۰٬۰۰۰")


class NotFoundPageTests(TestCase):
    def test_unknown_url_returns_custom_404(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertContains(response, "این نشانی در فروشگاه موجود نیست", status_code=404)
        self.assertContains(response, reverse("storefront:catalog"), status_code=404)

    def test_missing_product_uses_the_same_page(self):
        response = self.client.get(reverse("storefront:product-detail", args=[999999]))
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "این نشانی در فروشگاه موجود نیست", status_code=404)
