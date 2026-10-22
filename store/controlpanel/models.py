from django.db import models


class SiteConfiguration(models.Model):
    intro_video = models.FileField(upload_to="site/videos/", blank=True)
    shop_name = models.CharField(max_length=160, default="لوازم یدکی سبزی", verbose_name="نام فروشگاه")
    contact_phone = models.CharField(max_length=40, blank=True, verbose_name="شماره تماس")
    contact_mobile = models.CharField(max_length=40, blank=True, verbose_name="موبایل فروشگاه")
    contact_address = models.TextField(max_length=800, default="شوشتر، کوی نیرو، روبه‌روی اداره آب و فاضلاب", verbose_name="آدرس فروشگاه")
    contact_email = models.EmailField(blank=True, verbose_name="ایمیل فروشگاه")
    business_hours = models.CharField(max_length=200, blank=True, verbose_name="ساعات کاری")
    map_url = models.URLField(blank=True, verbose_name="لینک موقعیت روی نقشه")
    ai_api_key_encrypted = models.TextField(blank=True, default="", editable=False)
    chortke_api_key_encrypted = models.TextField(blank=True, default="", editable=False)
    ai_model = models.CharField(max_length=100, default="gpt-6-astra")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "تنظیمات سایت"
        verbose_name_plural = "تنظیمات سایت"

    def __str__(self):
        return "تنظیمات سایت"

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]


    def set_ai_api_key(self, raw_key):
        import base64
        import hashlib
        from cryptography.fernet import Fernet
        from django.conf import settings
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest())
        self.ai_api_key_encrypted = Fernet(key).encrypt(raw_key.encode("utf-8")).decode("ascii")

    def get_ai_api_key(self):
        if not self.ai_api_key_encrypted:
            return ""
        import base64
        import hashlib
        from cryptography.fernet import Fernet, InvalidToken
        from django.conf import settings
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest())
        try:
            return Fernet(key).decrypt(self.ai_api_key_encrypted.encode("ascii")).decode("utf-8")
        except InvalidToken:
            return ""

    def set_chortke_api_key(self, raw_key):
        self.chortke_api_key_encrypted = self._encrypt_secret(raw_key)

    def get_chortke_api_key(self):
        return self._decrypt_secret(self.chortke_api_key_encrypted)

    @staticmethod
    def _encrypt_secret(raw_key):
        import base64, hashlib
        from cryptography.fernet import Fernet
        from django.conf import settings
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest())
        return Fernet(key).encrypt(raw_key.encode("utf-8")).decode("ascii")

    @staticmethod
    def _decrypt_secret(encrypted):
        if not encrypted:
            return ""
        import base64, hashlib
        from cryptography.fernet import Fernet, InvalidToken
        from django.conf import settings
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest())
        try:
            return Fernet(key).decrypt(encrypted.encode("ascii")).decode("utf-8")
        except InvalidToken:
            return ""


class DailyStorySelection(models.Model):
    day = models.DateField(unique=True)
    product_ids = models.JSONField(default=list)


class Announcement(models.Model):
    title = models.CharField("عنوان", max_length=160)
    body = models.TextField("متن اطلاعیه", max_length=3000)
    is_active = models.BooleanField("نمایش در سایت", default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name = "اطلاعیه"
        verbose_name_plural = "اطلاعیه‌ها"

    def __str__(self):
        return self.title
