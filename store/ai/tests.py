import io
from types import SimpleNamespace
from datetime import date, timedelta
from unittest.mock import patch
from PIL import Image
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from store.accounts.models import User
from .models import ChatConversation, CustomerImageUsage
from .usage import image_usage, reserve_image_upload, usage_day


class CustomerAnswerCacheTests(TestCase):
    def setUp(self):
        cache.clear()

    def _config(self):
        return SimpleNamespace(ai_model="test-model", get_ai_api_key=lambda: "test-key")

    def _provider_response(self):
        response = SimpleNamespace(status_code=200)
        response.raise_for_status = lambda: None
        response.json = lambda: {"choices": [{"message": {"content": "پاسخ عمومی"}}]}
        return response

    def test_public_answers_share_only_within_the_approval_tier(self):
        from .services import ask_gapgpt
        approved_a = User.objects.create_user(username="09121111111", is_approved=True)
        approved_b = User.objects.create_user(username="09122222222", is_approved=True)
        guest = User.objects.create_user(username="09123333333", is_approved=False)
        messages = [("user", "سلام")]
        with patch("store.ai.services.find_products", return_value=[]), patch("store.ai.services.post_gapgpt", return_value=self._provider_response()) as provider:
            _, cached_a = ask_gapgpt(config=self._config(), messages=messages, user=approved_a)
            _, cached_b = ask_gapgpt(config=self._config(), messages=messages, user=approved_b)
            _, cached_guest = ask_gapgpt(config=self._config(), messages=messages, user=guest)
        self.assertFalse(cached_a)
        self.assertTrue(cached_b)
        self.assertFalse(cached_guest)
        self.assertEqual(provider.call_count, 2)

    def test_personal_account_answers_are_never_shared_from_cache(self):
        from .services import ask_gapgpt
        first = User.objects.create_user(username="09124444444", is_approved=True, debt=1000)
        second = User.objects.create_user(username="09125555555", is_approved=True, debt=0)
        messages = [("user", "مانده بدهی من چقدر است؟")]
        with patch("store.ai.services.find_products", return_value=[]), patch("store.ai.services.post_gapgpt", return_value=self._provider_response()) as provider:
            _, first_cached = ask_gapgpt(config=self._config(), messages=messages, user=first)
            _, second_cached = ask_gapgpt(config=self._config(), messages=messages, user=second)
        self.assertFalse(first_cached)
        self.assertFalse(second_cached)
        self.assertEqual(provider.call_count, 2)


class ImageQuotaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="09120000000", is_approved=True)
        self.client.force_login(self.user)
        self.conversation = ChatConversation.objects.create(user=self.user)
        session = self.client.session
        session["active_ai_conversation"] = self.conversation.pk
        session.save()
        stream = io.BytesIO()
        Image.new("RGB", (12, 12), "white").save(stream, "PNG")
        self.raw = stream.getvalue()

    def upload(self):
        return self.client.post(reverse("ai_assistant:customer-chat"), {"conversation_id": self.conversation.pk, "image": SimpleUploadedFile("sample.png", self.raw, content_type="image/png")})

    def test_five_uploads_then_blocked_without_provider_call(self):
        with patch("store.ai.views.extract_invoice_items", return_value=([], True)) as provider:
            for expected in range(1, 6):
                response = self.upload()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["image_usage"]["used"], expected)
            response = self.upload()
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.json()["image_usage"]["remaining"], 0)
            self.assertEqual(provider.call_count, 5)
        self.assertEqual(image_usage(self.user)["total"], 5)

    def test_durable_counts_and_separate_customers(self):
        other = User.objects.create_user(username="09129999999", is_approved=True)
        for _ in range(5):
            self.assertTrue(reserve_image_upload(self.user)[0])
        cache.clear()
        self.assertFalse(reserve_image_upload(self.user)[0])
        self.assertTrue(reserve_image_upload(other)[0])
        self.conversation.delete()
        self.assertEqual(image_usage(self.user)["total"], 5)

    def test_new_day_resets_daily_limit_and_keeps_total(self):
        today = date(2026, 10, 13)
        with patch("store.ai.usage.usage_day", return_value=today):
            for _ in range(5):
                reserve_image_upload(self.user)
            self.assertFalse(reserve_image_upload(self.user)[0])
        with patch("store.ai.usage.usage_day", return_value=today+timedelta(days=1)):
            accepted, usage = reserve_image_upload(self.user)
            self.assertTrue(accepted)
            self.assertEqual(usage["used"], 1)
            self.assertEqual(usage["total"], 6)

    def test_invalid_image_does_not_consume(self):
        response = self.client.post(reverse("ai_assistant:customer-chat"), {"conversation_id": self.conversation.pk, "image": SimpleUploadedFile("fake.png", b"not image", content_type="image/png")})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(image_usage(self.user)["total"], 0)

    def test_failure_still_counts_accepted_upload(self):
        with patch("store.ai.views.extract_invoice_items", side_effect=RuntimeError("offline")), patch("store.ai.views.logger.exception"):
            response = self.upload()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["image_usage"]["used"], 1)

    def test_unapproved_and_invalid_session_do_not_consume(self):
        self.user.is_approved = False
        self.user.save()
        self.assertEqual(self.upload().status_code, 403)
        self.user.is_approved = True
        self.user.save()
        session = self.client.session
        del session["active_ai_conversation"]
        session.save()
        self.assertEqual(self.upload().status_code, 400)
        self.assertEqual(image_usage(self.user)["total"], 0)

    def test_admin_report_and_thumbnail_markup(self):
        reserve_image_upload(self.user)
        staff = User.objects.create_user(username="manager", is_staff=True)
        self.assertEqual(self.client.get(reverse("controlpanel:image-usage")).status_code, 302)
        self.client.force_login(staff)
        response = self.client.get(reverse("controlpanel:image-usage"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_uploads"], 1)
        self.assertEqual(response.context["page_obj"].object_list[0].image_total, 1)
        self.assertContains(self.client.get(reverse("controlpanel:customers")), "کل تصاویر")

    def test_quota_status_endpoint(self):
        response = self.client.get(reverse("ai_assistant:customer-chat"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["image_usage"]["remaining"], 5)
        self.assertEqual(response["Cache-Control"], "private, no-store")
