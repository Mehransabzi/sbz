from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError


def normalize_mobile(value):
    value = value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    digits = "".join(char for char in value if char.isdigit())
    if digits.startswith("98") and len(digits) == 12:
        digits = "0" + digits[2:]
    elif len(digits) == 10 and digits.startswith("9"):
        digits = "0" + digits
    return digits


class RegistrationForm(forms.Form):
    first_name = forms.CharField(label="نام", max_length=150)
    last_name = forms.CharField(label="نام خانوادگی", max_length=150)
    phone = forms.CharField(label="شماره موبایل", max_length=24, widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"}))
    address = forms.CharField(label="آدرس", max_length=800, widget=forms.Textarea(attrs={"rows": 3, "autocomplete": "street-address"}))

    def clean_phone(self):
        phone = normalize_mobile(self.cleaned_data["phone"])
        if len(phone) != 11 or not phone.startswith("09"):
            raise ValidationError("شماره موبایل را به شکل ۰۹xxxxxxxxx وارد کنید.")
        if get_user_model().objects.filter(username=phone).exists():
            raise ValidationError("برای این شماره موبایل قبلاً حساب ساخته شده است.")
        return phone

    def save(self):
        User = get_user_model()
        phone = self.cleaned_data["phone"]
        return User.objects.create_user(username=phone, password=phone, phone=phone, first_name=self.cleaned_data["first_name"], last_name=self.cleaned_data["last_name"], address=self.cleaned_data["address"])


class MobileAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label="شماره موبایل", widget=forms.TextInput(attrs={"autofocus": True, "inputmode": "tel", "autocomplete": "username"}))

    def clean_username(self):
        raw = self.cleaned_data["username"].strip()
        phone = normalize_mobile(raw)
        return phone if len(phone) == 11 and phone.startswith("09") else raw
