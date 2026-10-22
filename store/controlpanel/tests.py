from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from store.catalog.models import Product
from store.ai.models import ChatConversation, ChatMessage, CustomerImageUsage
from store.integrations.chortke.models import SyncRun
from .content_services import daily_story_products

class ManagementFeatureTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(username='manager', is_staff=True)
        self.customer = get_user_model().objects.create_user(username='09121111111')
        self.client.force_login(self.staff)
        self.product = Product.objects.create(chortke_code='part1', name='قطعه', description='منبع')

    def test_background_sync_starts_once_and_returns_poll_url(self):
        with patch('subprocess.Popen') as process:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse('controlpanel:sync'), HTTP_ACCEPT='application/json')
            self.assertEqual(response.status_code, 200)
            process.assert_called_once()
            with self.captureOnCommitCallbacks(execute=True):
                second = self.client.post(reverse('controlpanel:sync'), HTTP_ACCEPT='application/json')
            self.assertEqual(second.json()['id'], response.json()['id'])
            process.assert_called_once()
            status = self.client.get(response.json()['status_url'])
            self.assertEqual(status.json()['status'], 'running')
            self.assertEqual(status['Cache-Control'], 'no-store')

    def test_launch_failure_is_recorded(self):
        with patch('subprocess.Popen', side_effect=OSError('unavailable')):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse('controlpanel:sync'), HTTP_ACCEPT='application/json')
        self.assertEqual(self.client.get(response.json()['status_url']).json()['status'], 'failed')

    def test_generated_description_is_draft_until_saved(self):
        url = reverse('controlpanel:product-description', args=[self.product.pk])
        with patch('store.controlpanel.content_services.generate_description', return_value={'description':'پیش‌نویس','sources':[]}):
            self.assertEqual(self.client.post(url, {'action':'generate'}).json()['description'], 'پیش‌نویس')
        self.product.refresh_from_db()
        self.assertEqual(self.product.description_override, '')
        self.client.post(url, {'action':'save', 'description':'توضیح جدید'})
        self.product.refresh_from_db()
        self.assertEqual(self.product.display_description, 'توضیح جدید')
        self.assertEqual(self.product.description, 'منبع')

    def test_story_selection_is_stable_and_eligible(self):
        for n in range(9):
            Product.objects.create(chortke_code=str(n), name='کالا', image_url='/media/x.webp')
        Product.objects.create(chortke_code='hidden', name='پنهان', image_url='/media/x.webp', is_visible=False)
        first = [p.pk for p in daily_story_products()]
        self.assertEqual(len(first), 5)
        self.assertEqual(first, [p.pk for p in daily_story_products()])
        self.assertNotIn(self.product.pk, first)
        self.assertTrue(all(p.is_visible and p.image_url for p in daily_story_products()))
        self.assertEqual(self.client.get(reverse('controlpanel:daily-stories')).status_code, 200)

    def test_delete_all_requires_confirmation_and_keeps_usage(self):
        conversation = ChatConversation.objects.create(user=self.customer)
        ChatMessage.objects.create(conversation=conversation, role='user', content='سلام')
        CustomerImageUsage.objects.create(user=self.customer, day=timezone.localdate(), count=3)
        url = reverse('controlpanel:ai-customer-chats-delete-all')
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.assertTrue(ChatConversation.objects.exists())
        self.client.post(url, {'confirmation':'DELETE'})
        self.assertFalse(ChatMessage.objects.exists())
        self.assertFalse(ChatConversation.objects.exists())
        self.assertEqual(CustomerImageUsage.objects.get().count, 3)

    def test_staff_pages_render_and_customer_is_denied(self):
        SyncRun.objects.create(status='warning', image_errors=[{'code':'8', 'reason':'HTTP 404'}])
        for name in ['sync-report','products','ai-customer-chats']:
            self.assertEqual(self.client.get(reverse('controlpanel:'+name)).status_code, 200)
        self.assertEqual(self.client.get(reverse('controlpanel:product-description', args=[self.product.pk])).status_code, 200)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse('controlpanel:daily-stories')).status_code, 302)
        self.assertEqual(self.client.post(reverse('controlpanel:ai-customer-chats-delete-all'), {'confirmation':'DELETE'}).status_code, 302)

    def test_sync_reports_progress_and_preserves_custom_description(self):
        from contextlib import nullcontext
        from unittest.mock import Mock
        from store.integrations.chortke.services import sync_catalog
        self.product.description_override = 'توضیح مدیر'
        self.product.save()
        provider = Mock(base_url='https://example.com')
        provider.get_products.return_value = [{'code':'part1', 'title':'قطعه جدید', 'description':'متن چرتکه', 'imageUrl':'/missing.jpg'}]
        observed = []
        def images(sources, **kwargs):
            kwargs['progress'](1, 1)
            observed.append(SyncRun.objects.first().progress)
            return 'test-generation', {}, [{'code':'part1', 'reason':'HTTP 404'}]
        with patch('store.integrations.chortke.services.catalog_sync_lock', return_value=nullcontext()), patch('store.integrations.chortke.services.prepare_images', side_effect=images), patch('store.integrations.chortke.services.prune_images'), patch('store.integrations.chortke.services.rebuild_index', return_value=0):
            run = sync_catalog(provider)
        self.assertEqual(observed, [60])
        self.assertEqual(run.progress, 100)
        self.assertEqual(run.status, 'warning')
        self.assertEqual(run.image_fallbacks[0]['name'], 'قطعه جدید')
        self.assertEqual(run.image_fallbacks[0]['fallback'], 'placeholder')
        self.assertEqual(run.image_errors, [])
        self.product.refresh_from_db()
        self.assertEqual(self.product.description_override, 'توضیح مدیر')
