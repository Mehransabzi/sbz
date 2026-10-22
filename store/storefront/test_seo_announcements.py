from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from store.catalog.models import Product
from store.controlpanel.models import Announcement


class PublicDiscoveryTests(TestCase):
    def test_install_manifest_and_worker(self):
        response = self.client.get('/manifest.webmanifest')
        self.assertEqual(response['Content-Type'], 'application/manifest+json')
        manifest = response.json()
        self.assertEqual(manifest['start_url'], '/')
        self.assertEqual({icon['sizes'] for icon in manifest['icons']}, {'192x192', '512x512'})
        response = self.client.get('/service-worker.js')
        self.assertEqual(response['Service-Worker-Allowed'], '/')
        self.assertEqual(response['Cache-Control'], 'no-cache')
        for path in ('/manifest.webmanifest', '/service-worker.js'):
            self.assertEqual(self.client.head(path).status_code, 200)
            self.assertEqual(self.client.post(path).status_code, 405)

    def test_robots_and_head(self):
        response = self.client.get('/robots.txt')
        self.assertContains(response, 'Sitemap: https://sbzpart.ir/sitemap.xml')
        for path in ('/admin/', '/panel/', '/accounts/'):
            self.assertContains(response, 'Disallow: ' + path)
        for path in ('/', '/catalog/', '/robots.txt', '/sitemap.xml'):
            self.assertEqual(self.client.head(path).status_code, 200)

    def locations(self):
        response = self.client.get('/sitemap.xml', HTTP_HOST='localhost')
        self.assertEqual(response.status_code, 200)
        root = ET.fromstring(response.content)
        return [node.text for node in root.findall('{*}url/{*}loc')]

    def test_sitemap_is_current_public_catalog(self):
        category = 'قطعات > برق & چراغ'
        product = Product.objects.create(chortke_code='PUBLIC', name='کالا', category=category)
        hidden = Product.objects.create(chortke_code='HIDDEN', name='مخفی', is_visible=False)
        inactive = Product.objects.create(chortke_code='INACTIVE', name='غیرفعال', is_active=False)
        urls = self.locations()
        self.assertIn('https://sbzpart.ir/', urls)
        self.assertIn('https://sbzpart.ir/catalog/', urls)
        self.assertIn('https://sbzpart.ir/catalog/?' + urlencode({'category': category}), urls)
        self.assertIn(f'https://sbzpart.ir/products/{product.pk}/', urls)
        for item in (hidden, inactive):
            self.assertNotIn(f'https://sbzpart.ir/products/{item.pk}/', urls)
        fresh = Product.objects.create(chortke_code='SYNCED', name='جدید')
        self.assertIn(f'https://sbzpart.ir/products/{fresh.pk}/', self.locations())
        product.is_active = False
        product.save()
        self.assertNotIn(f'https://sbzpart.ir/products/{product.pk}/', self.locations())

    def test_canonical_keeps_category_and_drops_tracking(self):
        params = {'category': 'چراغ', 'page': '2'}
        response = self.client.get('/catalog/', {**params, 'utm_source': 'test'})
        self.assertEqual(response.context['canonical_url'], 'https://sbzpart.ir/catalog/?' + urlencode(params))
        self.assertContains(response, 'rel="canonical"')
        response = self.client.get('/catalog/?page=1')
        self.assertEqual(response.context['canonical_url'], 'https://sbzpart.ir/catalog/')


class AnnouncementTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(username='notice-manager', is_staff=True)
        self.customer = get_user_model().objects.create_user(username='notice-customer')
        self.url = reverse('controlpanel:announcements')

    def test_staff_can_create_edit_disable_and_delete(self):
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(self.url), 'اطلاعیه جدید')
        response = self.client.post(self.url, {'title': 'اطلاعیه', 'body': 'متن جدید', 'is_active': 'on'})
        self.assertRedirects(response, self.url)
        item = Announcement.objects.get()
        self.assertContains(self.client.get('/'), item.body)
        response = self.client.post(reverse('controlpanel:announcement-edit', args=[item.pk]),
                                    {'title': 'ویرایش', 'body': 'متن غیرفعال'})
        self.assertRedirects(response, self.url)
        self.assertNotContains(self.client.get('/'), 'متن غیرفعال')
        delete = reverse('controlpanel:announcement-delete', args=[item.pk])
        self.assertEqual(self.client.get(delete).status_code, 405)
        self.assertRedirects(self.client.post(delete), self.url)
        self.assertFalse(Announcement.objects.exists())

    def test_customer_and_anonymous_cannot_manage(self):
        item = Announcement.objects.create(title='عمومی', body='متن')
        for user in (None, self.customer):
            if user:
                self.client.force_login(user)
            for url in (self.url, reverse('controlpanel:announcement-edit', args=[item.pk]),
                        reverse('controlpanel:announcement-delete', args=[item.pk])):
                self.assertEqual(self.client.get(url).status_code, 302)
                self.assertEqual(self.client.post(url, {'title': 'bad', 'body': 'bad'}).status_code, 302)
        self.assertEqual(Announcement.objects.get().title, 'عمومی')

    def test_validation_and_escaped_public_content(self):
        self.client.force_login(self.manager)
        response = self.client.post(self.url, {'title': '', 'body': ''})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Announcement.objects.exists())
        Announcement.objects.create(title='<script>alert(1)</script>', body='<img src=x onerror=alert(1)>\nسطر دوم')
        Announcement.objects.create(title='HIDDEN NOTICE', body='secret', is_active=False)
        response = self.client.get('/')
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertNotContains(response, 'HIDDEN NOTICE')
        self.assertContains(response, '<br>سطر دوم', html=False)
