from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()
_digits = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


@register.filter
def fa_num(value):
    if value is None or value == "":
        return ""
    raw = str(value).strip().replace(",", "").replace("٬", "")
    sign = ""
    if raw.startswith(("-", "+")):
        sign, raw = raw[0], raw[1:]
    try:
        whole, dot, fraction = raw.partition(".")
        whole = str(int(whole or "0"))
        grouped = ""
        while whole:
            grouped = whole[-3:] + (("٬" + grouped) if grouped else "")
            whole = whole[:-3]
        rendered = grouped + (("٫" + fraction) if dot and fraction else "")
        return sign.translate(_digits) + rendered.translate(_digits)
    except (ValueError, InvalidOperation):
        return str(value).translate(_digits)

@register.filter
def fa_digits(value):
    return str(value or "").translate(_digits)
