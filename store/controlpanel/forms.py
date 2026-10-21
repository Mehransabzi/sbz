from pathlib import Path
from django import forms
from .models import SiteConfiguration


class SiteConfigurationForm(forms.ModelForm):
    ai_api_key = forms.CharField(label="کلید API گپ‌جی‌پی‌تی", required=False, strip=True, max_length=1000, widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password", "placeholder": "برای نگه‌داشتن کلید فعلی خالی بگذارید"}))
    chortke_api_key = forms.CharField(label="???? API ?????", required=False, strip=True, max_length=2000, widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}))
    class Meta:
        model = SiteConfiguration
        fields = ("shop_name", "contact_phone", "contact_mobile", "contact_address", "contact_email", "business_hours", "map_url", "intro_video", "ai_model")
        labels = {"ai_model": "شناسه مدل گپ‌جی‌پی‌تی", "intro_video": "ویدیوی معرفی فروشگاه"}
        widgets = {"intro_video": forms.ClearableFileInput(attrs={"accept": "video/mp4,video/webm,video/quicktime"})}

    def save(self, commit=True):
        instance = super().save(commit=False)
        key = self.cleaned_data.get("ai_api_key", "")
        if key:
            instance.set_ai_api_key(key)
        chortke_key = self.cleaned_data.get("chortke_api_key", "")
        if chortke_key:
            instance.set_chortke_api_key(chortke_key)
        if commit:
            instance.save()
            self.save_m2m()
        return instance

    def clean_intro_video(self):
        video = self.cleaned_data.get("intro_video")
        if not video or not hasattr(video, "name"):
            return video
        suffix = Path(video.name).suffix.lower()
        if suffix not in {".mp4", ".webm", ".mov"}:
            raise forms.ValidationError("فقط فایل ویدیویی MP4، WebM یا MOV قابل بارگذاری است.")
        if video.size > 250 * 1024 * 1024:
            raise forms.ValidationError("حجم ویدیو نباید بیشتر از ۲۵۰ مگابایت باشد.")
        return video


class CustomerDebtForm(forms.Form):
    debt = forms.DecimalField(label="کل مانده بدهی (ریال)", min_value=0, max_digits=18, decimal_places=0, widget=forms.TextInput(attrs={"inputmode": "numeric"}))


class ProductImageForm(forms.Form):
    image = forms.ImageField(
        label="انتخاب عکس کالا",
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp", "data-product-image-input": ""}),
    )

    def clean_image(self):
        from io import BytesIO
        import uuid
        import warnings
        from PIL import Image, ImageOps, UnidentifiedImageError
        from django.core.files.base import ContentFile

        upload = self.cleaned_data["image"]
        if upload.size > 12 * 1024 * 1024:
            raise forms.ValidationError("حجم عکس حداکثر ۱۲ مگابایت باشد.")
        try:
            upload.seek(0)
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(upload) as source:
                    if source.format not in {"JPEG", "PNG", "WEBP"}:
                        raise forms.ValidationError("عکس باید JPG، PNG یا WebP باشد.")
                    if source.width * source.height > 25_000_000:
                        raise forms.ValidationError("ابعاد عکس بیش از حد بزرگ است؛ عکس کوچک‌تری انتخاب کنید.")
                    image = ImageOps.exif_transpose(source)
                    image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                    image = image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB")
                    output = BytesIO()
                    image.save(output, format="WEBP", quality=80, method=6)
            return ContentFile(output.getvalue(), name=uuid.uuid4().hex + ".webp")
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise forms.ValidationError("عکس معتبر نیست؛ فایل دیگری انتخاب کنید.")
