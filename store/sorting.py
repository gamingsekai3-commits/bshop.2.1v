"""Shared "sort by" / "period" handling for every product listing page
(home, category, search).

Two query-string params, read straight off the request:

  ?sort=name_asc|name_desc|price_asc|price_desc|popularity|rating
  ?period=daily|monthly|yearly

Both are optional and have sensible defaults (name A-Z, all time), so a
plain listing URL with neither param still works exactly as before.
"""
from datetime import timedelta

from django.db.models import Case, DecimalField, F, Sum, When
from django.db.models.functions import Coalesce
from django.utils import timezone

SORT_CHOICES = ('name_asc', 'name_desc', 'price_asc', 'price_desc', 'popularity', 'rating')
PERIOD_CHOICES = ('daily', 'monthly', 'yearly')

# Rolling windows, not calendar boundaries - "monthly" means "added in the
# last 30 days", matching the "last 365 days" style used elsewhere on the
# site rather than requiring the visitor to think in calendar months.
PERIOD_DAYS = {'daily': 1, 'monthly': 30, 'yearly': 365}

# The price actually charged: the sale price when the product is on sale,
# otherwise the regular price. Sorting by "price" should reflect what a
# shopper actually pays, not the crossed-out original.
_EFFECTIVE_PRICE = Case(
    When(is_sale=True, then=F('sale_price')),
    default=F('price'),
    output_field=DecimalField(max_digits=10, decimal_places=2),
)


def apply_sort_and_period(queryset, request):
    """Apply ?sort= and ?period= from `request` to `queryset`, returning a
    new queryset. Safe to call on any Product queryset (active or not)."""

    period = request.GET.get('period')
    if period in PERIOD_CHOICES:
        since = timezone.now() - timedelta(days=PERIOD_DAYS[period])
        queryset = queryset.filter(created_at__gte=since)

    sort = request.GET.get('sort')
    if sort == 'name_desc':
        queryset = queryset.order_by('-name')
    elif sort == 'price_asc':
        queryset = queryset.annotate(_price=_EFFECTIVE_PRICE).order_by('_price')
    elif sort == 'price_desc':
        queryset = queryset.annotate(_price=_EFFECTIVE_PRICE).order_by('-_price')
    elif sort == 'popularity':
        # "Popular" = most units sold across all orders (reverse FK from
        # cart.OrderItem). Products never ordered still show up, just last.
        queryset = queryset.annotate(
            _sold=Coalesce(Sum('orderitem__quantity'), 0)
        ).order_by('-_sold', 'name')
    elif sort == 'rating':
        queryset = queryset.order_by('-rating', 'name')
    else:
        queryset = queryset.order_by('name')

    return queryset
