"""When is a product "out", "low" or "enough" in stock?

The answer depends on what the product costs. 5 left of a 3,000₮ pen is low,
but 1 or 2 left of a 67,000,000₮ car is a normal stock level. So every price
band below has its own "low" limit.

To change the rules, edit LOW_STOCK_TIERS - nothing else needs to be touched
(admin lists, the Stock page, the Reports, the dashboard and the storefront
badges all read from here).
"""
from decimal import Decimal

from django.db.models import Q

# (price from, "low" when stock is at most ...). The first band whose price
# is reached wins, so list them from the most expensive down.
#
#   price            low when stock is   meaning
#   10,000,000+      -                   even 1 unit is enough (car, motorcycle)
#   1,000,000+       1 - 2               expensive: a couple of units is enough
#   100,000+         1 - 5               mid-range
#   below 100,000    1 - 10              cheap: needs a bigger buffer
LOW_STOCK_TIERS = (
    (Decimal('10000000'), 0),
    (Decimal('1000000'), 2),
    (Decimal('100000'), 5),
    (Decimal('0'), 10),
)


def effective_price(price, is_sale, sale_price):
    """The price a customer really pays (sale price when on sale)."""
    return sale_price if is_sale and sale_price and sale_price > 0 else price


def low_stock_limit(price):
    """Highest stock count that still counts as "low" for this price."""
    price = Decimal(price or 0)
    for start, limit in LOW_STOCK_TIERS:
        if price >= start:
            return limit
    return LOW_STOCK_TIERS[-1][1]


def stock_state(stock, price):
    """'out' (none left), 'low' (running low for its price) or 'ok'."""
    if stock <= 0:
        return 'out'
    return 'low' if stock <= low_stock_limit(price) else 'ok'


# --- the same rules as database filters (for counts and list filters) -------

def _price_band_q(start, end):
    """Effective price in [start, end): sale price if on sale, else price."""
    on_sale = Q(is_sale=True, sale_price__gt=0)
    sale_band, regular_band = Q(sale_price__gte=start), Q(price__gte=start)
    if end is not None:
        sale_band &= Q(sale_price__lt=end)
        regular_band &= Q(price__lt=end)
    return (on_sale & sale_band) | (~on_sale & regular_band)


def out_q():
    return Q(stock=0)


def low_q():
    q, upper = Q(pk__in=[]), None
    for start, limit in LOW_STOCK_TIERS:
        if limit > 0:
            q |= _price_band_q(start, upper) & Q(stock__gt=0, stock__lte=limit)
        upper = start
    return q


def ok_q():
    return Q(stock__gt=0) & ~low_q()
