import io
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
