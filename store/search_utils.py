"""Search helpers: the main product search, "did you mean" spelling
correction, and the live suggestions shown while the visitor is typing.

Everything here is plain Django ORM + the standard library (difflib), so it
works on any database and needs no extra packages. It is designed for a
shop-sized catalogue (hundreds to a few thousand products). If the catalogue
grows much larger, swap `_vocabulary()` for PostgreSQL trigram search
(django.contrib.postgres, pg_trgm) or a search engine.
"""
import re
from difflib import get_close_matches

from django.db.models import Q
from django.urls import reverse

from .models import Category, Product

_WORD = re.compile(r'\w+', re.UNICODE)


def search_products(term):
    """The main search: name, description or category name contains `term`."""
    return Product.active.filter(
        Q(name__icontains=term) |
        Q(description__icontains=term) |
        Q(category__name__icontains=term)
    ).distinct()


def _vocabulary():
    """Every word used in active product and category names (lower-case)."""
    names = list(Product.active.values_list('name', flat=True))
    names += list(Category.active.values_list('name', flat=True))
    words = set()
    for name in names:
        words.update(w.lower() for w in _WORD.findall(name))
    return sorted(words)


def correct_query(query):
    """Spelling correction against the shop's own vocabulary.

    "sedna" -> "sedan", "red suvv" -> "red suv". Returns the corrected string,
    or None when nothing needed (or could be) corrected. A word that is already
    valid - or is the beginning of a valid word, because the visitor is still
    typing it - is left alone.
    """
    tokens = _WORD.findall(query.lower())
    if not tokens:
        return None

    words = _vocabulary()
    if not words:
        return None

    corrected, changed = [], False
    for token in tokens:
        if len(token) < 3 or any(w.startswith(token) for w in words):
            corrected.append(token)
            continue
        cutoff = 0.6 if len(token) >= 4 else 0.8
        match = get_close_matches(token, words, n=1, cutoff=cutoff)
        if match:
            corrected.append(match[0])
            changed = True
        else:
            corrected.append(token)

    return ' '.join(corrected) if changed else None


def _rank(text, query_lower):
    """0 = starts with the query, 1 = a word inside starts with it, 2 = contains it."""
    text = text.lower()
    if text.startswith(query_lower):
        return 0
    if any(w.startswith(query_lower) for w in _WORD.findall(text)):
        return 1
    return 2


def _matches(query, product_limit, category_limit):
    query_lower = query.lower()

    products = list(
        Product.active
        .filter(Q(name__icontains=query) | Q(category__name__icontains=query))
        .select_related('category')[:80]
    )
    # Best matches first: name starts with what was typed, then a word in the
    # name does, then the rest (in stock before out of stock at each level).
    products.sort(key=lambda p: (
        _rank(p.name, query_lower) if query_lower in p.name.lower() else 3,
        0 if p.stock > 0 else 1,
        p.name.lower(),
    ))

    categories = list(Category.active.filter(name__icontains=query)[:20])
    categories.sort(key=lambda c: (_rank(c.name, query_lower), c.name.lower()))

    return products[:product_limit], categories[:category_limit]


def _product_payload(product):
    on_sale = product.is_sale and product.sale_price > 0
    return {
        'name': product.name,
        'url': reverse('product_detail', args=[product.id]),
        'image': product.image.url if product.image else '',
        'price': int((product.sale_price if on_sale else product.price) or 0),
        'in_stock': product.stock > 0,
    }


def suggest(query, product_limit=6, category_limit=3):
    """Live suggestions for the search box.

    Returns products and categories that match what has been typed so far.
    If nothing matches, it retries with a spelling-corrected query and reports
    that as `did_you_mean`.
    """
    products, categories = _matches(query, product_limit, category_limit)
    did_you_mean = None

    if not products and not categories:
        corrected = correct_query(query)
        if corrected:
            products, categories = _matches(corrected, product_limit, category_limit)
            if products or categories:
                did_you_mean = corrected

    return {
        'did_you_mean': did_you_mean,
        'categories': [
            {'name': c.name, 'url': reverse('category', args=[c.name])}
            for c in categories
        ],
        'products': [_product_payload(p) for p in products],
    }
