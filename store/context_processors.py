from django.db.models import F, Q, Sum
from django.utils.functional import SimpleLazyObject

from .models import Category, Product, SearchHistory
from .translations import get_language, get_translations, AVAILABLE_LANGUAGES


def categories(request):
    """Makes the category list available in every template's context
    (used by navbar.html's 'Ангилал' dropdown on all pages)."""
    # Only active categories: switching one off in the admin removes it from
    # the navbar dropdown without deleting it or its products.
    return {'categories': Category.active.all()}


def language(request):
    """Makes the current language code (LANG), the translation dict for it
    (T), and the list of available languages available in every template."""
    return {
        'LANG': get_language(request),
        'T': get_translations(request),
        'AVAILABLE_LANGUAGES': AVAILABLE_LANGUAGES,
    }


# ---------------------------------------------------------------------------
# Search dropdown (recent searches + recommended products)
# ---------------------------------------------------------------------------
# navbar.html is included on EVERY page and it renders the search dropdown, so
# the data for that dropdown has to be available on every page too. It used to
# be passed only from the `search` view, which is why the history showed up on
# the search results page and nowhere else.

HISTORY_LIMIT = 10
RECOMMENDATION_LIMIT = 5


def _get_search_history(request):
    """Recent searches as a plain list of strings, newest first - the same
    shape for logged-in users (database) and visitors (session)."""
    if request.user.is_authenticated:
        return list(
            SearchHistory.objects.filter(user=request.user)
            .order_by('-created_at')
            .values_list('query', flat=True)[:HISTORY_LIMIT]
        )
    return list(request.session.get('search_history', []))[:HISTORY_LIMIT]


def _get_recommendations(history):
    """Up to RECOMMENDATION_LIMIT products to suggest in the dropdown.

    1. Products from the same categories as the visitor's recent searches
       (so someone who searched "car" sees more cars).
    2. Topped up with best sellers overall, then newest products, so the
       list is never empty - also for brand-new visitors with no history.

    Only active, in-stock products are suggested.
    """
    products = (
        Product.active.filter(stock__gt=0)
        .select_related('category')
        .annotate(sold=Sum(
            'orderitem__quantity',
            filter=Q(orderitem__order__status__in=['pending', 'confirmed', 'delivered']),
        ))
        .order_by(F('sold').desc(nulls_last=True), '-id')
    )

    picked, seen = [], set()

    def add(queryset):
        for product in queryset:
            if len(picked) >= RECOMMENDATION_LIMIT:
                return
            if product.id not in seen:
                seen.add(product.id)
                picked.append(product)

    terms = history[:5]
    if terms:
        match = Q()
        for term in terms:
            match |= Q(name__icontains=term) | Q(category__name__icontains=term)
        category_ids = list(
            Product.active.filter(match).values_list('category_id', flat=True).distinct()
        )
        if category_ids:
            add(products.filter(category_id__in=category_ids)[:RECOMMENDATION_LIMIT])

    add(products[:RECOMMENDATION_LIMIT])
    return picked


def search_dropdown(request):
    """Provides `search_history` and `search_recommendations` to every
    template. Both are lazy, so pages that never render the navbar (e.g. the
    admin) don't pay for the queries."""
    return {
        'search_history': SimpleLazyObject(lambda: _get_search_history(request)),
        'search_recommendations': SimpleLazyObject(
            lambda: _get_recommendations(_get_search_history(request))
        ),
    }
