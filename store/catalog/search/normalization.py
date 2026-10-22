import re
import unicodedata

STOP_WORDS = set("قیمت محصولات محصول کالا کالاها لطفا لطفاً میخوام میخواهم دارید دارین هست است برای از به رو را یک این اون مشابه پیدا کن کنید بگو بگید چند چنده چه کد شماره نمایش موجود موجودی انبار ببین ببینم من خودم سفارش سفارشات وضعیت آخر آخرین و با که در می باشد قطعه".split())
TRANSLATION = str.maketrans("يكآأإؤئةۀ۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "یکاااویه ه01234567890123456789".replace(" ", ""))
SYNONYMS = {"اویل": "روغن", "فیلترروغن": "فیلتر روغن", "پدترمز": "لنت", "بوجی": "شمع", "بلبرینگ": "بلبرینگ", "oil filter": "فیلتر روغن", "brake pad": "لنت", "spark plug": "شمع"}


def normalize(text):
    text = unicodedata.normalize("NFKC", str(text or "")).casefold().translate(TRANSLATION)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("\u200c", " ").replace("ـ", "")
    text = re.sub(r"(?<=\d)(?=[^\W\d_])|(?<=[^\W\d_])(?=\d)", " ", text)
    text = re.sub(r"[^\w\s]", " ", text).replace("_", " ")
    text = " ".join(text.split())
    for source, target in SYNONYMS.items():
        text = re.sub(r"(?<!\w)" + re.escape(source) + r"(?!\w)", target, text)
    return text


def query_tokens(text):
    return [token for token in normalize(text).split() if token not in STOP_WORDS][:16]


def document_text(product):
    values = [product.name, product.category, product.display_description[:2400], product.accounting_code, product.chortke_code, product.barcode, product.unit]
    if product.source_code and product.source_code not in values:
        values.append(product.source_code)
    return "\n".join(filter(None, values))
