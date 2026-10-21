from django import forms


class OrderForm(forms.Form):
    cart_items = forms.CharField(max_length=12000, widget=forms.HiddenInput)
    note = forms.CharField(
        max_length=1000,
        required=False,
        label="توضیحات (اختیاری)",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "اگر نکته‌ای درباره سفارش دارید بنویسید"}),
    )
