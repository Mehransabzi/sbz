"""Match upstream IDs without changing existing cart keys or order relations."""
from collections import Counter, defaultdict


def product_plan(items, previous, first_value):
    unique = {}
    skipped = 0
    repeated_rows = 0
    for item in items:
        source_id = str(first_value(item, "id", default="")).strip()
        code = str(first_value(item, "code", "accountingCode", default="")).strip()
        accounting = str(first_value(item, "accountingCode", default="")).strip()
        if not source_id and not code:
            skipped += 1
            continue
        if max(len(source_id), len(code), len(accounting)) > 100:
            raise ValueError("شناسه یا کد کالای چرتکه بیش از حد مجاز است.")
        identity = ("id", source_id) if source_id else ("code", code)
        if identity in unique:
            if unique[identity]["item"] != item:
                raise ValueError(f"چرتکه برای شناسه {source_id or code} اطلاعات متناقض فرستاده است؛ تغییری ذخیره نشد.")
            repeated_rows += 1
            continue
        unique[identity] = {"source_id": source_id or None, "source_code": code,
                            "accounting_code": accounting, "item": item, "previous": None}

    records = list(unique.values())
    by_id = {p.chortke_id: p for p in previous if p.chortke_id}
    by_code = {p.chortke_code: p for p in previous if not p.chortke_id}
    by_accounting = defaultdict(list)
    for product in previous:
        if product.accounting_code and not product.chortke_id:
            by_accounting[product.accounting_code].append(product)
    claimed = set()
    code_counts = Counter(r["source_code"] for r in records if r["source_code"])

    def attach(record, product):
        if product and product.pk not in claimed:
            record["previous"] = product
            record["key"] = product.chortke_code
            claimed.add(product.pk)

    # Reserve known IDs before adopting legacy records, independent of API order.
    for record in records:
        attach(record, by_id.get(record["source_id"]))
    for record in records:
        if record["previous"] is None and record["accounting_code"]:
            candidates = [p for p in by_accounting[record["accounting_code"]] if p.pk not in claimed]
            if len(candidates) == 1:
                attach(record, candidates[0])
    for record in reversed(records):
        if record["previous"] is None:
            candidate = by_code.get(record["source_code"])
            if candidate and (not candidate.accounting_code or not record["accounting_code"]
                              or candidate.accounting_code == record["accounting_code"]
                              or code_counts[record["source_code"]] == 1):
                attach(record, candidate)

    reserved = {p.chortke_code for p in previous}
    for record in records:
        if record["previous"] is None:
            candidates = (record["source_code"], record["accounting_code"],
                          "chortke-" + record["source_id"] if record["source_id"] else "")
            key = next((key for key in candidates if key and len(key) <= 100 and key not in reserved), None)
            if key is None:
                raise ValueError("شناسه یکتای امن برای کالا ساخته نشد؛ همگام‌سازی متوقف شد.")
            record["key"] = key
            reserved.add(key)
    shared_codes = [{"code": code, "count": count,
                     "products": [{"id": r["source_id"], "key": r["key"], "accounting_code": r["accounting_code"],
                                   "name": str(first_value(r["item"], "title", "name", default=code))[:255]}
                                  for r in records if r["source_code"] == code]}
                    for code, count in sorted(code_counts.items()) if count > 1]
    return records, skipped, repeated_rows, shared_codes
