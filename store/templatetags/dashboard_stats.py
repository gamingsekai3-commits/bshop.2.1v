import math
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django import template
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from cart.models import Order, OrderItem
from store.models import Category, Customer, Product

register = template.Library()


@register.simple_tag
def total_products():
    return Product.objects.count()


@register.simple_tag
def total_customers():
    return Customer.objects.count()


@register.simple_tag
def total_categories():
    return Category.objects.count()


@register.simple_tag
def total_orders():
    return Order.objects.count()


@register.simple_tag
def pending_orders():
    return Order.objects.filter(status=Order.STATUS_PENDING).count()


@register.simple_tag
def total_revenue():
    """Income: sum of (price * quantity) over DELIVERED orders only.

    An order that is pending, taken by a courier or assigned to one is not
    income yet; it becomes income when its status is "Хүргэлт дууссан".
    """
    total = OrderItem.objects.filter(order__status=Order.STATUS_DELIVERED).aggregate(
        total=Sum(
            ExpressionWrapper(
                F('price') * F('quantity'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
    )['total']
    return total or 0


@register.simple_tag
def low_stock_count():
    """Products that are sold out or running low (low depends on the price)."""
    from ..stock_rules import low_q, out_q
    return Product.objects.filter(out_q() | low_q()).count()


# Days and months are grouped in the shop's own time zone. settings.py keeps
# TIME_ZONE = 'UTC', which would start each "day" at 8 in the morning in
# Ulaanbaatar and put late-evening orders on the wrong bar.
SHOP_TZ = ZoneInfo('Asia/Ulaanbaatar')

# Bar chart drawing area, in SVG units. The width is chosen per chart (the
# two revenue charts sit side by side in a 4 : 3 split, so their widths are
# 760 and 570 and the text ends up the same size in both); the height is
# the same for both so the two cards line up.
_LEFT, _TOP, _BOTTOM, _PAD_RIGHT, _HEIGHT = 44, 24, 214, 10, 262
DAILY_WIDTH, MONTHLY_WIDTH = 760, 570


def _fmt(value):
    """Geometry goes into the template as ready-made strings. Floats given
    straight to a template are localised, and the Mongolian number format
    would turn 44.5 into 44,5 - which is not a valid SVG coordinate."""
    return f'{value:.1f}'


def _short_number(n):
    """1500000 -> '1.5M', 250000 -> '250K', 42 -> '42' (for axis labels)."""
    for size, suffix in ((10 ** 9, 'B'), (10 ** 6, 'M'), (10 ** 3, 'K')):
        if n >= size:
            return f'{n / size:.1f}'.rstrip('0').rstrip('.') + suffix
    return str(int(n))


def _grid_step(max_value, lines=4):
    """Smallest 'round' step (1, 2, 5, 10, 20, 50 ...) so that `lines`
    grid lines cover the tallest bar."""
    for power in range(0, 13):
        for mult in (1, 2, 5):
            step = mult * 10 ** power
            if step * lines >= max_value:
                return step
    return int(max_value)


def _bar_layout(values, width, value_fmt=str, lines=4):
    """Turn a list of numbers into bar-chart geometry (grid lines plus one
    dict of coordinates per bar). Shared by every bar chart on the dashboard;
    the caller adds its own labels and tooltips to each bar."""
    step = _grid_step(max(values + [0]), lines)
    top_value = step * lines

    plot_w = width - _PAD_RIGHT - _LEFT
    plot_h = _BOTTOM - _TOP
    slot = plot_w / len(values)
    bar_w = slot * 0.6

    grid = []
    for i in range(lines + 1):
        y = _BOTTOM - plot_h * i / lines
        grid.append({'y': _fmt(y), 'text_y': _fmt(y + 4), 'label': value_fmt(step * i)})

    bars = []
    for i, v in enumerate(values):
        h = plot_h * v / top_value
        bars.append({
            'slot_x': _fmt(_LEFT + i * slot),
            'slot_w': _fmt(slot),
            'x': _fmt(_LEFT + i * slot + (slot - bar_w) / 2),
            'w': _fmt(bar_w),
            'y': _fmt(_BOTTOM - h),
            'h': _fmt(h),
            'cx': _fmt(_LEFT + i * slot + slot / 2),
            'value_y': _fmt(_BOTTOM - h - 6),
            'value_label': value_fmt(v),
        })
    return grid, bars


def _chart_frame(width):
    return {
        'width': width,
        'height': _HEIGHT,
        # below this the chart scrolls sideways instead of shrinking its text
        'min_width': int(width * 0.8),
        'left': _LEFT,
        'right': width - _PAD_RIGHT,
        'top': _TOP,
        'bottom': _BOTTOM,
        'plot_h': _BOTTOM - _TOP,
    }


def _item_value():
    """price * quantity of an order item, as a Decimal expression."""
    return ExpressionWrapper(
        F('price') * F('quantity'),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )


@register.simple_tag
def revenue_by_day(days=14):
    """Revenue (sum of price * quantity) per day for the last `days` days,
    already laid out as bar-chart geometry for the dashboard.

    Only delivered orders count, on the day they were delivered, to match the
    Revenue card at the top of the dashboard (total_revenue above).
    """
    today = timezone.now().astimezone(SHOP_TZ).date()
    first_day = today - timedelta(days=days - 1)
    since = datetime.combine(first_day, time.min, tzinfo=SHOP_TZ)

    revenue = dict(
        OrderItem.objects.filter(
            order__status=Order.STATUS_DELIVERED, order__delivered_at__gte=since)
        .order_by()
        .annotate(day=TruncDate('order__delivered_at', tzinfo=SHOP_TZ))
        .values_list('day')
        .annotate(total=Sum(_item_value()))
    )
    orders = dict(
        Order.objects.filter(created_at__gte=since)
        .order_by()
        .annotate(day=TruncDate('created_at', tzinfo=SHOP_TZ))
        .values_list('day')
        .annotate(n=Count('id'))
    )

    day_list = [first_day + timedelta(days=i) for i in range(days)]
    values = [int(revenue.get(d) or 0) for d in day_list]
    grid, bars = _bar_layout(values, DAILY_WIDTH, value_fmt=_short_number)
    for d, value, bar in zip(day_list, values, bars):
        bar.update({
            'revenue': value,
            'orders': orders.get(d, 0),
            'name': d.strftime('%Y-%m-%d'),   # shown in the tooltip
            'label': d.strftime('%m-%d'),     # shown under the bar
            'year': '',
            'is_current': d == today,
        })

    return {
        'days': days,
        'total': sum(values),
        'grid': grid,
        'bars': bars,
        **_chart_frame(DAILY_WIDTH),
    }


def _months_back(day, back):
    """First day of the month that is `back` months before `day`'s month."""
    index = day.year * 12 + (day.month - 1) - back
    return date(index // 12, index % 12 + 1, 1)


@register.simple_tag
def revenue_by_month(months=12):
    """Revenue (sum of price * quantity) per calendar month for the last
    `months` months, the current, still-running month included.

    Only delivered orders count, in the month they were delivered, to match
    the Revenue card at the top of the dashboard (total_revenue above).
    """
    today = timezone.now().astimezone(SHOP_TZ).date()
    month_list = [_months_back(today, months - 1 - i) for i in range(months)]
    since = datetime.combine(month_list[0], time.min, tzinfo=SHOP_TZ)

    # Grouped per day in the database, then added up per month here. That
    # keeps the time-zone handling identical to revenue_by_day and is at most
    # ~365 rows.
    per_day_revenue = (
        OrderItem.objects.filter(
            order__status=Order.STATUS_DELIVERED, order__delivered_at__gte=since)
        .order_by()
        .annotate(day=TruncDate('order__delivered_at', tzinfo=SHOP_TZ))
        .values_list('day')
        .annotate(total=Sum(_item_value()))
    )
    per_day_orders = (
        Order.objects.filter(created_at__gte=since)
        .order_by()
        .annotate(day=TruncDate('created_at', tzinfo=SHOP_TZ))
        .values_list('day')
        .annotate(n=Count('id'))
    )
    revenue, orders = {}, {}
    for day, total in per_day_revenue:
        key = (day.year, day.month)
        revenue[key] = revenue.get(key, 0) + int(total or 0)
    for day, n in per_day_orders:
        key = (day.year, day.month)
        orders[key] = orders.get(key, 0) + n

    keys = [(m.year, m.month) for m in month_list]
    grid, bars = _bar_layout([revenue.get(k, 0) for k in keys], MONTHLY_WIDTH, value_fmt=_short_number)
    for m, key, bar in zip(month_list, keys, bars):
        bar.update({
            'revenue': revenue.get(key, 0),
            'orders': orders.get(key, 0),
            'name': m.strftime('%Y-%m'),
            # Twelve labels do not fit as '2026-09' in the narrower chart, so
            # the bar shows just the month and the year goes on a second line
            # under the first bar and under every January.
            'label': m.strftime('%m'),
            'year': str(m.year) if (m.month == 1 or m == month_list[0]) else '',
            'is_current': (m.year, m.month) == (today.year, today.month),
        })

    return {
        'months': months,
        'total': sum(revenue.get(k, 0) for k in keys),
        'grid': grid,
        'bars': bars,
        **_chart_frame(MONTHLY_WIDTH),
    }
