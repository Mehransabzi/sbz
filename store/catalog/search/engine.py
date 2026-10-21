import hashlib
import logging
import math
from collections import Counter
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Max, Case, When, IntegerField
from rapidfuzz.distance import DamerauLevenshtein
from store.catalog.models import Product, ProductEmbedding
from .embeddings import query_vector, cosine
from .indexing import fingerprint
from .normalization import normalize, query_tokens

logger = logging.getLogger(__name__)


def _snapshot():
    state = Product.objects.aggregate(count=Count("pk"), latest=Max("synced_at"))
    embedding_state = ProductEmbedding.objects.aggregate(latest=Max("updated_at"))
    revision = hashlib.sha256(str((state, embedding_state, settings.SEARCH_EMBEDDING_MODEL)).encode()).hexdigest()
    key = "catalog-search-snapshot:" + revision
    rows = cache.get(key)
    if rows is not None:
        return rows
    rows = []
    for product in Product.objects.select_related("search_embedding").all():
        try:
            stored = product.search_embedding
            vector = stored.vector if stored.model_name == settings.SEARCH_EMBEDDING_MODEL and stored.content_hash == fingerprint(product) else []
        except ProductEmbedding.DoesNotExist:
            vector = []
        name = normalize(product.name)
        rows.append({"id": product.pk, "name": name, "name_tokens": name.split(), "category_tokens": normalize(product.category).split(), "description_tokens": normalize(product.display_description[:2400]).split(), "codes": [normalize(value).replace(" ", "") for value in (product.chortke_code, product.accounting_code, product.barcode) if value], "vector": vector})
    cache.set(key, rows, 90)
    return rows


def _token_score(token, words):
    best = 0.0
    for word in words:
        if token == word:
            return 1.0
        if token.isdigit() or word.isdigit():
            continue
        if len(token) >= 3 and (word.startswith(token) or token.startswith(word)):
            best = max(best, 0.9 * min(len(token), len(word)) / max(len(token), len(word)) + 0.1)
        if len(token) == len(word) and len(token) >= 3:
            for i in range(len(token) - 1):
                if token[:i] + token[i+1] + token[i] + token[i+2:] == word:
                    best = max(best, .85)
        if min(len(token), len(word)) >= 3:
            similarity = DamerauLevenshtein.normalized_similarity(token, word, score_cutoff=0.6)
            if similarity >= (0.65 if len(token) >= 5 else 0.74):
                best = max(best, similarity)
    return best


def lexical_score(tokens, row, weights=None):
    scores = []
    for token in tokens:
        score = max(_token_score(token, row["name_tokens"]), _token_score(token, row["category_tokens"]) * .85, _token_score(token, row["description_tokens"]) * .72)
        scores.append(score)
    if not scores:
        return 0.0, 0.0
    coverage = sum(score >= .6 for score in scores) / len(scores)
    # Word order is intentionally ignored. One strong term cannot hide missing terms.
    token_weights = [weights.get(token, 1.0) for token in tokens] if weights else [1.0] * len(tokens)
    mean = sum(score * weight for score, weight in zip(scores, token_weights)) / sum(token_weights)
    return mean * (.55 + .45 * coverage), coverage


def ranked_product_ids(question, *, queryset=None, limit=None):
    question = str(question)[:500]
    tokens = query_tokens(question)
    if not tokens:
        return []
    queryset = queryset if queryset is not None else Product.objects.filter(is_active=True, is_visible=True)
    eligible = set(queryset.values_list("pk", flat=True))
    rows = [row for row in _snapshot() if row["id"] in eligible]
    compact = normalize(question).replace(" ", "")
    exact_ids = [row["id"] for row in rows if compact in row["codes"]]
    if exact_ids:
        return exact_ids[:limit] if limit is not None else exact_ids
    vocabulary = Counter(word for row in rows for word in row["name_tokens"] + row["category_tokens"])
    weights = {word: 1 + math.log(1 + len(rows) / frequency) for word, frequency in vocabulary.items()}
    vector = None
    matching_tokens = tokens
    if getattr(settings, "SEARCH_SEMANTIC_ENABLED", True) and any(row["vector"] for row in rows):
        try:
            # Correct unknown words before embedding so short typos retain meaning.
            semantic_tokens = []
            for token in tokens:
                corrected = token
                if token not in vocabulary and len(token) >= 3 and not token.isdigit():
                    choices = [(_token_score(token, [word]), frequency, word) for word, frequency in vocabulary.items() if len(word) >= 3 and DamerauLevenshtein.distance(token, word, score_cutoff=1) <= 1]
                    if choices:
                        similarity, _, candidate = max(choices)
                        if similarity >= .66:
                            corrected = candidate
                semantic_tokens.append(corrected)
            matching_tokens = semantic_tokens
            vector = query_vector(" ".join(semantic_tokens))
        except Exception:
            logger.warning("Semantic search unavailable; using typo-tolerant lexical matching.", exc_info=False)
    ranked = []
    numeric = {token for token in tokens if token.isdigit()}
    for row in rows:
        exact_code = compact in row["codes"]
        partial_code = len(compact) >= 3 and any(compact in code for code in row["codes"])
        if exact_code:
            ranked.append((4.0, row["name"], row["id"]))
            continue
        lexical, coverage = lexical_score(matching_tokens, row, weights)
        semantic = cosine(vector, row["vector"]) if vector else 0.0
        named_numbers = {word for word in row["name_tokens"] if word.isdigit()}
        if numeric and named_numbers and not numeric.intersection(named_numbers) and not partial_code:
            continue
        if not partial_code and not (lexical >= .44 and coverage >= .5) and semantic < .42:
            continue
        semantic_weight = max(0.0, min(1.0, (semantic - .2) / .5))
        score = lexical * .8 + semantic_weight * .2
        if partial_code:
            score = max(score, 1.2)
        if " ".join(tokens) in row["name"]:
            score += .2
        ranked.append((score, row["name"], row["id"]))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    ids = [row[2] for row in ranked]
    return ids[:limit] if limit is not None else ids


def search_products(question, *, queryset=None, limit=None):
    queryset = queryset if queryset is not None else Product.objects.filter(is_active=True, is_visible=True)
    ids = ranked_product_ids(question, queryset=queryset, limit=limit)
    if not ids:
        return queryset.none()
    ordering = Case(*[When(pk=pk, then=position) for position, pk in enumerate(ids)], output_field=IntegerField())
    return queryset.filter(pk__in=ids).order_by(ordering)
