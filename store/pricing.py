"""How much is added on top of the purchase price to get the selling price?

The dearer the product was to buy, the smaller the mark-up; the cheaper, the
bigger:

    purchase price (cost)      mark-up
    10,000₮ or less            30 %
    between                    slides smoothly (log scale) from 30 % down to 20 %
    10,000,000₮ or more        20 %

Example: a 3,000₮ pen gets 30 %, a 100,000₮ headset about 26.7 %, a 1,000,000₮
laptop about 23.3 %, a 67,000,000₮ car 20 %.

To change the rule edit the four constants below - nothing else needs to be
touched (the Stock page, the product admin and its "re-price" action all read
from here).
"""
import math
from decimal import Decimal, ROUND_CEILING

MARKUP_MAX = Decimal('30')              # % added to the cheapest goods
MARKUP_MIN = Decimal('20')              # % added to the dearest goods
LOW_COST = Decimal('10000')             # cost at/below which MARKUP_MAX applies
HIGH_COST = Decimal('10000000')         # cost at/above which MARKUP_MIN applies
ROUND_TO = Decimal('10')                # selling price is rounded UP to a multiple of this (₮)


def markup_percent(cost):
    """Mark-up in % (a Decimal between MARKUP_MIN and MARKUP_MAX) for this cost."""
    cost = Decimal(cost or 0)
    if cost <= LOW_COST:
        return MARKUP_MAX
    if cost >= HIGH_COST:
        return MARKUP_MIN
    # Position of the cost between LOW_COST and HIGH_COST on a log scale, 0..1.
    # (Log, because 100k -> 200k matters as much as 10k -> 20k does.)
    t = (math.log(cost) - math.log(LOW_COST)) / (math.log(HIGH_COST) - math.log(LOW_COST))
    return MARKUP_MAX - (MARKUP_MAX - MARKUP_MIN) * Decimal(str(round(t, 6)))


def selling_price(cost):
    """Cost + mark-up, rounded up to ROUND_TO. Returns None when there is no
    cost to work from (cost <= 0), so callers keep the price they already have."""
    cost = Decimal(cost or 0)
    if cost <= 0:
        return None
    raw = cost * (Decimal('1') + markup_percent(cost) / Decimal('100'))
    return (raw / ROUND_TO).to_integral_value(rounding=ROUND_CEILING) * ROUND_TO


def margin_percent(price, cost):
    """Actual mark-up of a price over its cost, in % (None if cost is 0)."""
    cost, price = Decimal(cost or 0), Decimal(price or 0)
    if cost <= 0:
        return None
    return (price - cost) / cost * Decimal('100')


def js_config():
    """The constants as plain numbers, so the Stock page can show the same
    live preview in JavaScript."""
    return {
        'max': float(MARKUP_MAX), 'min': float(MARKUP_MIN),
        'low': float(LOW_COST), 'high': float(HIGH_COST), 'round': float(ROUND_TO),
    }
