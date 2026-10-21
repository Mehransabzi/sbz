import logging

from django.core.cache import cache
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from store.accounts.decorators import approved_customer_required
from store.accounts.permissions import can_view_prices
from store.controlpanel.models import SiteConfiguration
from .models import ChatConversation, ChatMessage
from .usage import image_usage, reserve_image_upload
from .services import ask_gapgpt, extract_invoice_items, find_products, local_customer_reply

logger = logging.getLogger(__name__)


def _messages(data):
    rows = data.get("messages")
    if not isinstance(rows, list) or not rows or len(rows) > 14:
        return None
    cleaned = []
    for row in rows:
        if not isinstance(row, dict) or row.get("role") not in {"user", "assistant"}:
            return None
        text = row.get("content")
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            return None
        cleaned.append((row["role"], text.strip()))
    if sum(len(text) for _, text in cleaned) > 16000 or cleaned[-1][0] != "user":
        return None
    return cleaned


def _rate_limit(user):
    key = f"gapgpt-rate:{user.pk}"
    count = cache.get(key, 0)
    if count >= 30:
        return False
    cache.set(key, count + 1, 60)
    return True


class CustomerChatView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request):
        if not can_view_prices(request.user):
            return Response({"error": "حساب شما تأیید نشده است."}, status=403)
        response = Response({"image_usage": image_usage(request.user)})
        response["Cache-Control"] = "private, no-store"
        return response

    def post(self, request):
        if not can_view_prices(request.user):
            return Response({"error": "استفاده از ربات فقط برای حساب‌های تأییدشده فعال است."}, status=403)
        if request.data.get("action") == "product_search":
            query = str(request.data.get("query", "")).strip()[:255]
            if len(query) < 2:
                return Response({"products": []})
            lookup_key = f"gapgpt-product-lookup-rate:{request.user.pk}"
            lookup_count = cache.get(lookup_key, 0)
            if lookup_count >= 120:
                return Response({"error": "تعداد جست‌وجوها زیاد است؛ کمی بعد دوباره تلاش کنید."}, status=429)
            cache.set(lookup_key, lookup_count + 1, 60)
            matches = find_products(query, limit=8)
            return Response({"products": [{"id": p.pk, "code": p.chortke_code, "name": p.name, "unit": p.unit or "عدد", "price": int(p.sale_price), "image": p.display_image_url} for p in matches]})

        message = request.data.get("message", "")
        image = request.FILES.get("image")
        conversation_id = request.data.get("conversation_id")
        if image is None and (not isinstance(message, str) or not message.strip() or len(message) > 4000):
            return Response({"error": "پیام معتبر نیست یا بیش از حد طولانی است."}, status=400)
        if image is not None:
            if image.size > 6 * 1024 * 1024:
                return Response({"error": "حجم تصویر باید حداکثر ۶ مگابایت باشد."}, status=400)
            if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
                return Response({"error": "فرمت تصویر باید JPG، PNG یا WEBP باشد."}, status=400)
        if not _rate_limit(request.user):
            return Response({"error": "تعداد پیام‌ها زیاد است. یک دقیقه دیگر دوباره تلاش کنید."}, status=429)
        if str(request.session.get("active_ai_conversation", "")) != str(conversation_id):
            return Response({"error": "برای ادامه، صفحه ربات را دوباره باز کنید."}, status=400)
        conversation = get_object_or_404(ChatConversation, pk=conversation_id, user=request.user)
        if image is not None:
            from PIL import Image, UnidentifiedImageError
            import warnings
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(image) as source:
                        if source.format not in {"JPEG", "PNG", "WEBP"} or source.width * source.height > 30_000_000:
                            raise ValueError("invalid image")
                        source.verify()
                image.seek(0)
            except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
                return Response({"error": "فایل تصویر معتبر نیست یا ابعاد آن بیش از حد مجاز است."}, status=400)
            # Reserve before provider work; every accepted upload consumes one attempt.
            accepted, usage = reserve_image_upload(request.user)
            if not accepted:
                return Response({"error": "سهمیه امروز شما تمام شده است. روزانه ۵ تصویر می‌توانید ارسال کنید؛ از ساعت ۰۰:۰۰ به وقت ایران سهمیه تازه فعال می‌شود.", "image_usage": usage}, status=429)
            try:
                recognized, cached = extract_invoice_items(SiteConfiguration.current(), image.read(), image.content_type)
            except Exception:
                logger.exception("Customer invoice image analysis failed")
                return Response({"error": "بررسی تصویر فعلاً تکمیل نشد. این ارسال در سهمیه امروز شما ثبت شده است.", "image_usage": usage}, status=503)
            proposals = []
            for recognized_item in recognized:
                matches = find_products(recognized_item["name"], limit=4)
                choices = [{"id": p.pk, "code": p.chortke_code, "name": p.name, "unit": p.unit or "عدد", "price": int(p.sale_price), "image": p.display_image_url} for p in matches]
                proposals.append({"recognized_name": recognized_item["name"], "quantity": recognized_item["quantity"], "matches": choices})
            conversation.messages.create(role="user", content="تصویر فاکتور/فهرست خرید ارسال شد.")
            reply = "تصویر بررسی شد. اقلام پیشنهادی را بررسی و اصلاح کنید؛ چیزی تا تأیید شما به سبد خرید اضافه نمی‌شود." if proposals else "متن تصویر خوانده شد، اما قلمی با نام قابل تطبیق پیدا نشد. می‌توانید نام کالا را در کاتالوگ جست‌وجو کنید."
            conversation.messages.create(role="assistant", content=reply)
            if not conversation.title:
                conversation.title = "بررسی تصویر فاکتور"
                conversation.save(update_fields=["title", "updated_at"])
            return Response({"reply": reply, "cached": cached, "invoice_items": proposals, "image_usage": usage})
        text = message.strip()
        prior = list(conversation.messages.order_by("-created_at", "-pk").values("role", "content")[:14])
        prior.reverse()
        conversation.messages.create(role="user", content=text)
        messages = [(row["role"], row["content"]) for row in prior] + [("user", text)]
        if not conversation.title:
            conversation.title = text[:160]
            conversation.save(update_fields=["title", "updated_at"])
        try:
            answer, cached = ask_gapgpt(config=SiteConfiguration.current(), messages=messages, user=request.user)
            maintenance = False
        except Exception:
            logger.exception("Customer GapGPT request failed")
            products = find_products(text)
            answer = local_customer_reply(request.user, text, products)
            cached = False
            maintenance = True
        conversation.messages.create(role="assistant", content=answer[:12000])
        conversation.save(update_fields=["updated_at"])
        return Response({"reply": answer, "cached": cached, "maintenance": maintenance})


class NewCustomerConversationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not can_view_prices(request.user):
            return Response({"error": "استفاده از ربات فقط برای حساب‌های تأییدشده فعال است."}, status=403)
        conversation = ChatConversation.objects.create(user=request.user)
        request.session["active_ai_conversation"] = conversation.pk
        return Response({"url": reverse("storefront:smart-bot") + f"?conversation={conversation.pk}"})


class AdminAnalysisView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        messages = _messages(request.data)
        if messages is None:
            return Response({"error": "گفت‌وگو معتبر نیست."}, status=400)
        if not _rate_limit(request.user):
            return Response({"error": "تعداد پیام‌ها زیاد است. یک دقیقه دیگر دوباره تلاش کنید."}, status=429)
        try:
            answer, cached = ask_gapgpt(config=SiteConfiguration.current(), messages=messages, admin_mode=True, admin_reference=request.data.get("conversation_id"))
        except Exception as exc:
            logger.exception("Admin GapGPT analysis failed")
            text = str(exc) if isinstance(exc, RuntimeError) else "ارتباط با سرویس هوش مصنوعی ناموفق بود. تنظیمات و اتصال را بررسی کنید."
            return Response({"error": text}, status=503)
        return Response({"reply": answer, "cached": cached})


@approved_customer_required
@require_GET
def customer_chat_page(request):
    requested_id = request.GET.get("conversation")
    conversation = None
    if requested_id:
        conversation = ChatConversation.objects.filter(pk=requested_id, user=request.user, messages__isnull=True).first()
    if conversation is None:
        conversation = ChatConversation.objects.create(user=request.user)
    request.session["active_ai_conversation"] = conversation.pk
    return render(request, "ai/customer_chat.html", {"conversation": conversation, "image_usage": image_usage(request.user)})
