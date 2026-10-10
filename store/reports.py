"""Admin "Reports" (Тайлан) group.

The sidebar group is built in store/admin_site.py from the REPORTS list at the
bottom of this file. To add another report: write a view function like the two
below, add one line to REPORTS and add its name to translations.py - the
sidebar link, URL and permission check all follow from that.

Every view gets (site, request) and returns a TemplateResponse rendered with
templates/admin/report.html, so all reports share one layout and one date
filter. Views are wrapped in site.admin_view(), i.e. staff login required,
exactly like the built-in admin pages.
"""

import calendar
import json
import math
from collections import namedtuple
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.contrib.humanize.templatetags.humanize import intcomma
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Q, Sum, Value
from django.db.models.functions import Coalesce, NullIf, TruncDate
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from .pager import paginate_rows
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone

from cart.models import Order, OrderItem
from .barcode import code128c_svg
from .models import Product, StockEntry
from .sorting import apply_sort_and_period
from .templatetags.dashboard_stats import SHOP_TZ
from .translations import get_language, get_translations, translate_category_name

TAX_RATE = Decimal('0.02')   # 2% tax added on the customer receipt

# Column filter modes, read by static/admin/js/table-filter.js through the
# data-filter attribute that report.html puts on every <th>:
#   NO_FILTER - header click still sorts, but there is no funnel icon
#   LIST      - funnel with the tick-list of the column's values (status, ...)
#   COUNT     - funnel with fixed buckets 0-9 / 10-19 / 20-29 / 30+  (stock, units sold)
#   MONEY     - funnel with intervals worked out from the column's own lowest and
#               highest value, e.g. 100,000-500,000 / 500,000-1,000,000 ... (price)
NO_FILTER, LIST, COUNT, MONEY = 'none', 'list', 'count', 'money'
# Fourth item of every column tuple: does clicking the header sort the column?
SORT, NO_SORT = True, False

LINE_TOTAL = ExpressionWrapper(
    F('price') * F('quantity'),
    output_field=DecimalField(max_digits=14, decimal_places=2),
)


def _parse_date(value, fallback):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return fallback


def _month_start(d):
    return d.replace(day=1)


def _month_end(d):
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def _date_range(request):
    """(date_from, date_to) from ?date_from=&date_to=.

    Default is the current month in the shop's time zone: the 1st through
    the last day of the month. If only one of the two is given, the other
    falls on the matching edge of that same month. If they are entered the
    wrong way round they are swapped."""
    today = timezone.now().astimezone(SHOP_TZ).date()
    date_from = _parse_date(request.GET.get('date_from'), None)
    date_to = _parse_date(request.GET.get('date_to'), None)
    if date_from is None and date_to is None:
        date_from, date_to = _month_start(today), _month_end(today)
    elif date_from is None:
        date_from = _month_start(date_to)
    elif date_to is None:
        date_to = _month_end(date_from)
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    return date_from, date_to


def _bounds(date_from, date_to):
    """Whole days in the shop's own time zone, as aware datetimes. (The DB
    and settings.TIME_ZONE are UTC, which would cut each day at 8 am in
    Ulaanbaatar.) `date_to` is inclusive, so the upper bound is the start of
    the next day."""
    start = datetime.combine(date_from, time.min, tzinfo=SHOP_TZ)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=SHOP_TZ)
    return start, end


Link = namedtuple('Link', 'text url')      # a table cell that opens a detail popup

# What a summary card shows when clicked: a two-column list of the records
# behind its number, e.g. Detail('Ner', 'Uldegdel', [('LG 88800', 27), ...]).
# A summary item is (label, value) or (label, value, Detail / OrdersDetail);
# without the third part the card is not clickable.
# rows may carry a third value when extra_head is given.
Detail = namedtuple('Detail', 'name_head value_head rows extra_head', defaults=(None,))
# ...or, for order cards: the full orders (who ordered, what, how much) - see _order_cards().
OrdersDetail = namedtuple('OrdersDetail', 'orders')


def _cell(value):
    """One table cell -> (text, is_number, url). Numbers get thousands
    separators and are right-aligned by the template; a Link cell keeps its
    url so the template can render it as a clickable name."""
    if isinstance(value, Link):
        return (value.text, False, value.url)
    if value is None:
        return ('—', False, None)
    if isinstance(value, datetime):        # e.g. last-sold / last-order: show the shop-local date
        return (value.astimezone(SHOP_TZ).date().isoformat(), False, None)
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return (value.isoformat() if isinstance(value, date) else str(value), False, None)
    return (intcomma(round(value)), True, None)


def _detail_url(request, name, pk):
    """Link to a detail popup, carrying the report's date range along so the
    popup shows the same period as the table it was opened from."""
    date_from, date_to = _date_range(request)
    query = urlencode({'date_from': date_from.isoformat(), 'date_to': date_to.isoformat()})
    return f"{reverse(f'admin:{name}', args=[pk])}?{query}"


def _sort_value(value):
    """What a raw cell is compared by when its column is sorted. None means
    "empty" - those rows always go last, whichever way the column is sorted."""
    if isinstance(value, Link):
        value = value.text
    if value is None or value == '' or value == '—':
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value).casefold()


def _sort_attr(value):
    """(key, is_number) written on every body cell as data-sv / data-n, so the
    browser can re-order the rows it already has with exactly the same keys
    _sort_rows uses on the server. key '' means an empty cell (always last)."""
    key = _sort_value(value)
    if key is None:
        return '', False
    if isinstance(key, float):
        return repr(key), True
    return key, False


# --------------------------------------------------------------------------
# Column filters (funnel icon in a header)
# --------------------------------------------------------------------------
# Filtering is done HERE, on the report's whole row list and before it is cut
# into pages, so a filter covers every page (like sorting does) and the pager
# text ("Үр дүн: 1 - 1 / 1") matches what is on screen.
#
# URL: ?f<column number>=<value>, repeated for several values, e.g.
#   ?f2=0&f2=1        price intervals no. 0 and 1 (COUNT / MONEY columns)
#   ?f4=Бага          status = "Бага" (LIST columns)
# No f<n> for a column means "everything allowed".

COUNT_EDGES = (9, 19, 29)          # 0-9 / 10-19 / 20-29 / 30+
MAX_MONEY_BUCKETS = 6


def _money_edges(values):
    """Interval edges for a money column, from its lowest and highest value.

    Returns [e0, e1, ... en]: bucket i is e(i) .. e(i+1). The step is the
    smallest "round" one (1, 2 or 5 x 10^k) that covers min..max in at most
    MAX_MONEY_BUCKETS intervals, so prices of 120,000 .. 1,450,000 give
    100,000 / 500,000 / 1,000,000 / 1,500,000 style edges."""
    values = [v for v in values if v is not None]
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [lo, hi]
    exp = 0
    while True:
        for mult in (1, 2, 5):
            step = mult * 10 ** exp
            start = math.floor(lo / step) * step
            count = max(1, math.ceil((hi - start) / step))
            if count <= MAX_MONEY_BUCKETS:
                return [start + step * i for i in range(count + 1)]
        exp += 1


def _bucket_index(value, edges):
    """Which interval a value falls in (upper edge inclusive); -1 = none."""
    if value is None or len(edges) < 2:
        return -1
    for i in range(1, len(edges)):
        if value <= edges[i]:
            return i - 1
    return len(edges) - 2


def _filter_rows(request, rows, columns, lang):
    """Apply every ?f<col>= filter to `rows` (raw values, before _cell).

    Returns (rows, info) where info[i] is None for a column without a funnel,
    otherwise a dict the template hands to table-filter.js:
        {param, kind, options: [labels], values: [what the URL carries], selected: [..]}
    The options are built from ALL rows, not the filtered ones, so ticking
    one box never makes the other boxes disappear."""
    en = lang == 'en'
    info, tests = [], []
    for i, (_heading, _is_num, mode, _s) in enumerate(columns):
        param = f'f{i}'
        chosen = request.GET.getlist(param)
        if mode == COUNT:
            labels = ['0 – 9', '10 – 19', '20 – 29', '30 and up' if en else '30-с дээш']
            values = [str(n) for n in range(len(labels))]
            edges = [0, *COUNT_EDGES, math.inf]
            test = lambda v, e=edges: _bucket_index(v, e)
            keyf = lambda r, c=i: _sort_value(r[c])
        elif mode == MONEY:
            edges = _money_edges([_sort_value(r[i]) for r in rows])
            if len(edges) < 2:
                labels = []
            elif edges[0] == edges[-1]:
                labels = [f'{edges[0]:,.0f}']
            else:
                labels = [f'{edges[k]:,.0f} – {edges[k + 1]:,.0f}' for k in range(len(edges) - 1)]
            values = [str(n) for n in range(len(labels))]
            test = lambda v, e=edges: _bucket_index(v, e)
            keyf = lambda r, c=i: _sort_value(r[c])
        elif mode == LIST:
            seen = []
            for r in rows:
                text = _cell(r[i])[0]
                if text not in seen:
                    seen.append(text)
            seen.sort(key=lambda t: t.casefold())
            labels = [('(empty)' if en else '(хоосон)') if t in ('', '—') else t for t in seen]
            values = seen
            test = None
            keyf = lambda r, c=i: _cell(r[c])[0]
        else:
            info.append(None)
            continue

        selected = [v for v in chosen if v in values]
        info.append({'param': param, 'kind': 'list' if mode == LIST else 'range',
                     'options': labels, 'values': values, 'selected': selected})
        # Everything ticked (or nothing chosen) = no filter on this column.
        if selected and len(selected) < len(values):
            if mode == LIST:
                allowed = set(selected)
                tests.append(lambda r, k=keyf, a=allowed: k(r) in a)
            else:
                allowed = {int(v) for v in selected}
                tests.append(lambda r, k=keyf, t=test, a=allowed: t(k(r)) in a)
    if tests:
        rows = [r for r in rows if all(t(r) for t in tests)]
    return rows, info


def _sort_rows(request, rows, columns, filter_info=None):
    """Sort the report's WHOLE row list (before it is cut into pages) by the
    column in ?sort=<column number>&dir=asc|desc, so the order holds across
    every page and not only the 10 rows on screen. Returns (rows, columns_for_
    the_template) where each column also carries its header link and mark.

    Click cycle on a header, same as everywhere else: ascending -> descending
    -> back to the report's own order."""
    try:
        col = int(request.GET.get('sort', ''))
    except ValueError:
        col = -1
    if not 0 <= col < len(columns):
        col = -1
    direction = 'desc' if request.GET.get('dir') == 'desc' else 'asc'

    if col >= 0:
        keyed = [(_sort_value(r[col]), r) for r in rows]
        filled = [kr for kr in keyed if kr[0] is not None]
        empty = [r for k, r in keyed if k is None]
        try:
            filled.sort(key=lambda kr: kr[0], reverse=direction == 'desc')
        except TypeError:                              # mixed types in one column: fall back to text
            filled.sort(key=lambda kr: str(kr[0]), reverse=direction == 'desc')
        rows = [r for _k, r in filled] + empty

    def url_for_dir(i, wanted):
        """Link that puts column i into direction `wanted` ('asc' / 'desc'), or
        clears the sort when it is already in that direction."""
        params = request.GET.copy()
        params.pop('p', None)                          # a new order starts on page 1
        if col == i and direction == wanted:
            params.pop('sort', None)
            params.pop('dir', None)
        else:
            params['sort'], params['dir'] = str(i), wanted
        return request.path + ('?' + params.urlencode() if params else '')

    def url_for(i):
        # Header text: ascending -> descending -> back to the report's own order
        # (asking for 'desc' on a column that is already descending clears it).
        return url_for_dir(i, 'desc' if col == i else 'asc')

    out = []
    for i, (heading, is_num, filter_mode, _sortable) in enumerate(columns):
        # Every column sorts (the old per-column "sortable" flag is ignored).
        fdata = filter_info[i] if filter_info else None
        out.append((heading, is_num, filter_mode, True, url_for(i),
                    direction if col == i else '', col == i,
                    json.dumps(fdata, ensure_ascii=False) if fdata else '',
                    bool(fdata and fdata['selected'] and len(fdata['selected']) < len(fdata['values'])),
                    url_for_dir(i, 'asc'), url_for_dir(i, 'desc')))
    return rows, out


def _render(site, request, title_key, template_extra, *, show_filter=True, note_key=None):
    T = get_translations(request)
    if 'rows' in template_extra:
        rows, filter_info = _filter_rows(request, list(template_extra['rows']),
                                         template_extra['columns'], get_language(request))
        # Position of every row in the report's own order (after filtering, before
        # sorting): the browser needs it to undo a sort and to break ties like we do.
        original = {id(r): n for n, r in enumerate(rows)}
        template_extra['rows'], template_extra['columns'] = _sort_rows(
            request, rows, template_extra['columns'], filter_info)
        # cell = (text, is_number, url, sort key, key is a number, original position)
        all_rows = [[_cell(c) + _sort_attr(c) + (original[id(row)],) for c in row]
                    for row in template_extra['rows']]
        # Only one page of rows goes to the template; footer and summary cards
        # below/above are built from the full data, so they stay the same.
        template_extra['rows'], template_extra['pager'] = paginate_rows(request, all_rows)
    if 'summary' in template_extra:
        cards = []
        for item in template_extra['summary']:
            detail = item[2] if len(item) > 2 else None
            if isinstance(detail, OrdersDetail):
                detail = {'kind': 'orders', 'orders': detail.orders}
            elif detail is not None:
                heads = [detail.name_head, detail.value_head] + ([detail.extra_head] if detail.extra_head else [])
                detail = {'kind': 'table', 'heads': heads,
                          'rows': [[_cell(x) for x in row] for row in detail.rows]}
            cards.append((_cell(item[0]), _cell(item[1]), detail))
        template_extra['summary'] = cards
    if template_extra.get('footer'):
        template_extra['footer'] = [_cell(c) for c in template_extra['footer']]
    date_from, date_to = _date_range(request)
    context = {
        **site.each_context(request),
        'title': T[title_key],
        'report_title': T[title_key],
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'show_filter': show_filter,
        'note': T.get(note_key, '') if note_key else '',
        **template_extra,
    }
    return TemplateResponse(request, 'admin/report.html', context)


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------
# Cancelled orders are left out of every money / count figure below.

def _period_items(request):
    date_from, date_to = _date_range(request)
    start, end = _bounds(date_from, date_to)
    return OrderItem.objects.filter(
        order__created_at__gte=start, order__created_at__lt=end,
    ).exclude(order__status=Order.STATUS_CANCELLED)


def _income_items(request):
    """Order lines that count as INCOME in the selected period: only orders
    marked "Хүргэлт дууссан", on the day they were delivered. Taken / assigned
    / pending orders are not income."""
    date_from, date_to = _date_range(request)
    start, end = _bounds(date_from, date_to)
    return OrderItem.objects.filter(
        order__status=Order.STATUS_DELIVERED,
        order__delivered_at__gte=start, order__delivered_at__lt=end,
    )


def _ranked(name_head, value_head, pairs, biggest_first=True):
    """A Detail whose rows are sorted by their value."""
    return Detail(name_head, value_head,
                  sorted(pairs, key=lambda r: r[1], reverse=biggest_first))


def inventory_report(site, request):
    """Агуулах / Бараа: stock level, value and units sold in the period."""
    T = get_translations(request)
    period = (
        _period_items(request).values('product')
        .annotate(units=Sum('quantity'), last_sold=Max('order__created_at'))
    )
    sold = {r['product']: r['units'] for r in period}
    last_sold = {r['product']: r['last_sold'] for r in period}

    # Same ?sort= / ?period= controls as the storefront (store/sorting.py):
    # a-z, price, popularity (all-time units sold), rating - plus a
    # daily/monthly/yearly "added" filter. Leaving both off keeps the plain
    # A-Z listing below.
    products = apply_sort_and_period(Product.objects.select_related('category'), request)

    rows, total_units, total_value, low, out = [], 0, 0, 0, 0
    entries = []          # (name, stock, stock value, units sold, is low) - feeds the card popups
    for p in products:
        # The summary cards below count EVERY product in the store (sold or
        # not, in stock or sold out). The table itself only lists products
        # that sold in the selected period and still have stock.
        price = p.sale_price if p.is_sale and p.sale_price > 0 else p.price
        state = p.stock_state          # price-aware, see store/stock_rules.py
        if state == 'out':
            status, out = T['admin_out_of_stock'], out + 1
        elif state == 'low':
            status, low = T['admin_low'], low + 1
        else:
            status = T['admin_in_stock']
        total_units += p.stock
        total_value += price * p.stock
        entries.append((p.name, p.stock, price * p.stock, sold.get(p.id, 0), state == 'low', state == 'ok'))
        if not sold.get(p.id) or p.stock == 0:
            continue
        rows.append((Link(p.name, _detail_url(request, 'report_product_detail', p.pk)),
                     translate_category_name(p.category.name, get_language(request)),
                     price, p.stock, status, sold.get(p.id, 0),
                     last_sold.get(p.id) or ''))   # never sold in the period: leave the cell empty, no dash

    return _render(site, request, 'admin_report_inventory', {
        'summary': [
            (T['admin_total_products'], len(entries),
             _ranked(T['admin_col_name'], T['admin_report_units_sold'], [(e[0], e[3]) for e in entries])),
            (T['admin_total_stock_units'], total_units,
             _ranked(T['admin_col_name'], T['admin_col_stock'], [(e[0], e[1]) for e in entries])),
            (T['admin_total_stock_value'], total_value,
             _ranked(T['admin_col_name'], T['admin_total_stock_value'], [(e[0], e[2]) for e in entries])),
            (T['admin_low_stock_status'], low,
             _ranked(T['admin_col_name'], T['admin_col_stock'], [(e[0], e[1]) for e in entries if e[4]],
                     biggest_first=False)),
            (T['admin_out_of_stock'], out,
             Detail(T['admin_col_name'], T['admin_col_stock'],
                    [(e[0], e[1]) for e in entries if e[1] == 0])),
            (T['admin_in_stock'], sum(1 for e in entries if e[5]),
             _ranked(T['admin_col_name'], T['admin_col_stock'],
                     [(e[0], e[1]) for e in entries if e[5]])),
        ],
        'columns': [
            (T['admin_col_name'], False, NO_FILTER, SORT),
            (T['admin_col_category'], False, LIST, NO_SORT),      # filter only
            (T['admin_col_price'], True, MONEY, SORT),
            (T['admin_col_stock'], True, COUNT, SORT),
            (T['admin_col_status'], False, LIST, NO_SORT),        # filter only: Дууссан / Бага / Хангалттай
            (T['admin_report_units_sold'], True, COUNT, SORT),
            (T['admin_report_last_sold'], False, NO_FILTER, SORT),
        ],
        'rows': rows,
    })


def _order_cards(T, orders):
    """Orders -> plain dicts for the card popups: who ordered (name, phone,
    address, account), what they bought and the amount (items only, no tax -
    the same basis as the Орлого card)."""
    cards = []
    for o in orders:
        items, total = [], 0
        for it in o.items.all():
            amount = it.price * it.quantity
            total += amount
            items.append({
                'name': it.name or (it.product.name if it.product else '—'), 'options': it.options,
                'qty': it.quantity, 'price': _money(it.price), 'amount': _money(amount),
            })
        cards.append({
            'id': o.id, 'date': _local(o.created_at), 'status': _status_label(T, o.status),
            'name': o.name, 'phone': o.phone, 'address': o.address,
            'username': o.user.username if o.user else '', 'items': items, 'total': _money(total),
        })
    return cards


def orders_report(site, request):
    """Захиалга: delivered orders, units and revenue per day.

    Everything here counts DELIVERED orders, on the day they were delivered
    (the same rule as revenue / income), so a day's orders, units and revenue
    always describe the same deliveries. Pending orders have their own card."""
    T = get_translations(request)
    items = _income_items(request)          # lines of delivered orders, by delivery day
    rows = sorted((
        {'day': r['day'], 'orders': r['orders'], 'units': r['units'], 'revenue': r['revenue']}
        for r in (
            items
            .annotate(day=TruncDate('order__delivered_at', tzinfo=SHOP_TZ))
            .values('day')
            .annotate(orders=Count('order', distinct=True), units=Sum('quantity'),
                      revenue=Sum(LINE_TOTAL))
            .order_by()
        )
    ), key=lambda r: r['day'], reverse=True)
    total_orders = items.values('order').distinct().count()
    total_units = sum(r['units'] or 0 for r in rows)
    total_revenue = sum(r['revenue'] or 0 for r in rows)
    average = (total_revenue / total_orders) if total_orders else 0

    date_from, date_to = _date_range(request)
    start, end = _bounds(date_from, date_to)
    order_qs = Order.objects.select_related('user').prefetch_related('items__product')
    order_cards = _order_cards(T, order_qs.filter(pk__in=items.values('order')))
    # Pending = still waiting, so it is counted by the day it was placed.
    pending_cards = _order_cards(T, order_qs.filter(
        created_at__gte=start, created_at__lt=end, status=Order.STATUS_PENDING))
    pending = len(pending_cards)
    # "Дууссан": delivered in the period - the same orders as the Orders card.
    completed = len(order_cards)

    # Which products made up "Зарагдсан (ш)": units and amount per product.
    by_product = {}
    for r in items.values('product', 'product__name', 'name').annotate(
            units=Sum('quantity'), revenue=Sum(LINE_TOTAL)):
        entry = by_product.setdefault(
            r['product'] or ('name', r['name']), [r['product__name'] or r['name'] or '—', 0, 0])
        entry[1] += r['units'] or 0
        entry[2] += r['revenue'] or 0
    sold_rows = sorted(by_product.values(), key=lambda e: (-e[1], e[0]))

    return _render(site, request, 'admin_report_orders', {
        # Орлого and the average order have no popup (no third item).
        'summary': [
            (T['admin_revenue'], total_revenue),
            (T['admin_orders'], total_orders, OrdersDetail(order_cards)),
            (T['admin_report_units_sold'], total_units, Detail(
                T['admin_col_name'], T['admin_report_units_sold'], sold_rows, T['admin_revenue'])),
            (T['admin_report_avg_order'], average),
            (T['admin_pending_orders'], pending, OrdersDetail(pending_cards)),
            (T['admin_completed_orders'], completed, OrdersDetail(order_cards)),
        ],
        'columns': [
            (T['admin_report_date'], False, NO_FILTER, SORT),
            (T['admin_orders'], True, NO_FILTER, SORT),
            (T['admin_report_units_sold'], True, NO_FILTER, SORT),
            (T['admin_revenue'], True, NO_FILTER, SORT),
        ],
        'rows': [(r['day'], r['orders'], r['units'], r['revenue']) for r in rows],
        'footer': (T['admin_report_total'], total_orders, total_units, total_revenue),
    }, note_key='admin_report_orders_note')


def _contact(user):
    """(phone, address) for any account - customer, admin/staff or driver -
    taken from whichever profile has it."""
    profiles = [getattr(user, n, None) for n in ('customer_profile', 'employee_profile', 'driver_profile')]
    phone = next((p.phone for p in profiles if p is not None and getattr(p, 'phone', '')), '')
    address = next((p.address for p in profiles if p is not None and getattr(p, 'address', '')), '')
    return phone, address


def customers_report(site, request):
    """Хэрэглэгч: every account that bought something in the period, with
    their orders and spending. Admins/staff and drivers count too - they can
    order like anyone else, so this works from the User, not the Customer table."""
    T = get_translations(request)
    date_from, date_to = _date_range(request)
    start, end = _bounds(date_from, date_to)
    # Positive filter (status IN ...) instead of exclude(): negating across a
    # multi-valued relation makes Django build a subquery per customer.
    counted = Q(
        orders__created_at__gte=start, orders__created_at__lt=end,
        orders__status__in=[
            Order.STATUS_PENDING, Order.STATUS_CONFIRMED, Order.STATUS_DELIVERED],
    )
    customers = list(
        get_user_model().objects
        .select_related('customer_profile', 'employee_profile', 'driver_profile')
        .annotate(
            order_count=Count('orders', filter=counted, distinct=True),
            spent=Sum(
                ExpressionWrapper(
                    F('orders__items__price') * F('orders__items__quantity'),
                    output_field=DecimalField(max_digits=14, decimal_places=2)),
                filter=counted & Q(orders__status=Order.STATUS_DELIVERED)),
            last_order=Max('orders__created_at', filter=counted),
        )
        # Only accounts that actually bought something in the period.
        .filter(order_count__gt=0)
        .order_by(F('spent').desc(nulls_last=True), 'username')
    )

    def _who(u, text):
        return Link(text, _detail_url(request, 'report_customer_detail', u.pk)) if text else text

    rows = [(
        _who(u, u.username), _who(u, u.get_full_name()), _contact(u)[0], u.order_count, u.spent or 0,
        T['admin_active'] if u.is_active else T['admin_inactive'], u.last_order,
    ) for u in customers]
    who = lambda u: u.get_full_name() or u.username
    nm, orders_head = T['admin_col_name'], T['admin_orders']

    return _render(site, request, 'admin_report_customers', {
        'summary': [
            (T['admin_total_customers'], len(customers), Detail(
                nm, T['admin_col_status'],
                [(who(u), T['admin_active'] if u.is_active else T['admin_inactive']) for u in customers])),
            (T['admin_active'], sum(1 for u in customers if u.is_active), Detail(
                nm, orders_head, [(who(u), u.order_count) for u in customers if u.is_active])),
            (T['admin_revenue'], sum(u.spent or 0 for u in customers), Detail(
                nm, T['admin_report_spent'], [(who(u), u.spent) for u in customers if u.spent])),
        ],
        'columns': [
            (T['admin_report_username'], False, NO_FILTER, NO_SORT),
            (T['admin_col_name'], False, NO_FILTER, SORT),
            (T['customer_phone'], False, NO_FILTER, NO_SORT),
            (T['admin_orders'], True, NO_FILTER, SORT),
            (T['admin_report_spent'], True, NO_FILTER, SORT),
            (T['admin_col_status'], False, LIST, NO_SORT),        # filter only
            (T['admin_report_last_order'], False, NO_FILTER, SORT),
        ],
        'rows': rows,
    }, note_key='admin_report_note')



# --------------------------------------------------------------------------
# Detail popups (opened by clicking a product / customer name in a report)
# --------------------------------------------------------------------------
# These return an HTML fragment that report.html loads into a modal. Same
# period (?date_from=&date_to=) as the report they were opened from.

def _money(value):
    return intcomma(round(value or 0))


def _local(dt):
    return dt.astimezone(SHOP_TZ).strftime('%Y-%m-%d %H:%M')


def _image_url(product):
    try:
        return product.image.url if product and product.image else ''
    except ValueError:
        return ''


def _status_label(T, status):
    return T.get(f'rd_status_{status}', status)


PRODUCT_DETAIL_ROWS = 50   # newest order lines listed in the product popup


def product_detail_response(request, product, start=None, end=None, period_label=''):
    """The product detail popup. With start/end (a report's date range) the
    sales figures cover that period; without them they cover all time - which
    is what the Product list page uses."""
    T = get_translations(request)
    lines_qs = OrderItem.objects.filter(product=product).exclude(order__status=Order.STATUS_CANCELLED)
    if start is not None:
        lines_qs = lines_qs.filter(order__created_at__gte=start, order__created_at__lt=end)
    totals = lines_qs.aggregate(units=Sum('quantity'), revenue=Sum(LINE_TOTAL), lines=Count('id'))
    lines = list(lines_qs.select_related('order').order_by('-order__created_at')[:PRODUCT_DETAIL_ROWS])

    on_sale = product.is_sale and product.sale_price > 0
    info = [
        (T['admin_col_name'], product.name),
        (T['admin_col_category'], translate_category_name(product.category.name, get_language(request))),
        (T['admin_col_price'], _money(product.price) + ' ₮'),
    ]
    if on_sale:
        info.append((T['rd_sale_price'], _money(product.sale_price) + ' ₮'))
    info += [
        (T['admin_col_stock'], product.stock),
        (T['admin_col_status'], T['admin_active'] if product.is_active else T['admin_inactive']),
        (T['rd_rating'], product.rating),
        (T['rd_added'], _local(product.created_at) if product.created_at else '—'),
    ]
    options = {}
    for opt in product.options.filter(is_active=True):
        options.setdefault(opt.option_type, []).append(opt.value)
    if options:
        info.append((T['rd_options'], '; '.join(f"{k}: {', '.join(v)}" for k, v in options.items())))

    return TemplateResponse(request, 'admin/report_detail_product.html', {
        'T': T, 'product': product, 'image_url': _image_url(product), 'info': info,
        'period': period_label, 'units': totals['units'] or 0, 'revenue': _money(totals['revenue']),
        'truncated': (totals['lines'] or 0) > PRODUCT_DETAIL_ROWS,
        'sales': [{
            'order_id': i.order_id, 'date': _local(i.order.created_at), 'customer': i.order.name,
            'qty': i.quantity, 'price': _money(i.price), 'amount': _money(i.price * i.quantity),
            'status': _status_label(T, i.order.status),
        } for i in lines],
    })


def product_detail(site, request, pk):
    """Popup opened from a report table: sales for the report's period."""
    product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
    date_from, date_to = _date_range(request)
    start, end = _bounds(date_from, date_to)
    return product_detail_response(request, product, start, end,
                                   f'{date_from.isoformat()} – {date_to.isoformat()}')


def customer_detail(site, request, pk):
    T = get_translations(request)
    # pk is the User id: customers, admins and drivers can all have orders.
    user = get_object_or_404(
        get_user_model().objects.select_related('customer_profile', 'employee_profile', 'driver_profile'), pk=pk)
    date_from, date_to = _date_range(request)
    start, end = _bounds(date_from, date_to)
    # Same statuses the customers report counts (cancelled orders excluded).
    orders = list(
        Order.objects.filter(
            user=user, created_at__gte=start, created_at__lt=end,
            status__in=[Order.STATUS_PENDING, Order.STATUS_CONFIRMED, Order.STATUS_DELIVERED],
        ).prefetch_related('items__product').order_by('-created_at')
    )
    order_rows = []
    grand_subtotal = grand_tax = 0
    for o in orders:
        items, subtotal = [], 0
        for it in o.items.all():
            amount = it.price * it.quantity
            subtotal += amount
            items.append({
                'name': it.name or (it.product.name if it.product else '—'), 'options': it.options,
                'image_url': _image_url(it.product), 'qty': it.quantity,
                'price': _money(it.price), 'amount': _money(amount),
            })
        tax = (Decimal(subtotal) * TAX_RATE).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        grand_subtotal += subtotal
        grand_tax += tax
        stamp = o.created_at.astimezone(SHOP_TZ)
        slip = f'{o.id:06d}'
        order_rows.append({
            'id': o.id, 'slip': slip,
            'barcode_text': f"{slip}-{stamp:%Y%m%d}-{stamp:%H%M}",
            'barcode': mark_safe(code128c_svg(f"{slip}{stamp:%Y%m%d%H%M}")),
            'date': _local(o.created_at), 'status': _status_label(T, o.status),
            'name': o.name, 'phone': o.phone, 'address': o.address, 'items': items,
            'subtotal': _money(subtotal), 'tax': _money(tax), 'total': _money(subtotal + tax),
        })
    phone, address = _contact(user)
    info = [
        (T['admin_report_username'], user.username),
        (T['admin_col_name'], user.get_full_name() or '—'),
        (T['customer_phone'], phone or '—'),
        (T['rd_address'], address or '—'),
    ]
    return TemplateResponse(request, 'admin/report_detail_customer.html', {
        'T': T, 'info': info, 'orders': order_rows,
        'tax_percent': int(TAX_RATE * 100),
        'grand_subtotal': _money(grand_subtotal), 'grand_tax': _money(grand_tax),
        'grand_total': _money(grand_subtotal + grand_tax),
        'period': f'{date_from.isoformat()} – {date_to.isoformat()}',
    })


PIE_COLORS = ['#e8c84a', '#4a90d9', '#e0614b', '#4caf7d', '#9b6bd1', '#e8934a', '#3fb8c4', '#c4688f', '#8a8f98']


def _pie(slices, max_slices=8):
    """[(label, value)] -> pie-chart geometry for the template.

    Everything the SVG needs is built here as plain strings (a localised
    float like 44,5 would break an SVG coordinate). The smallest slices past
    `max_slices` are merged into one "Other" slice by the caller's label.
    """
    import math
    slices = [(l, v) for l, v in slices if v and v > 0]
    total = sum(v for _l, v in slices)
    if not total:
        return {'total': 0, 'slices': []}
    cx = cy = 100
    r = 90
    angle, out = -math.pi / 2, []
    for i, (label, value) in enumerate(slices):
        share = float(value) / float(total)
        sweep = share * 2 * math.pi
        x1, y1 = cx + r * math.cos(angle), cy + r * math.sin(angle)
        x2, y2 = cx + r * math.cos(angle + sweep), cy + r * math.sin(angle + sweep)
        out.append({
            'label': label, 'value': int(value), 'percent': f'{share * 100:.1f}',
            'color': PIE_COLORS[i % len(PIE_COLORS)], 'full': len(slices) == 1,
            'path': (f'M {cx} {cy} L {x1:.2f} {y1:.2f} '
                     f'A {r} {r} 0 {1 if sweep > math.pi else 0} 1 {x2:.2f} {y2:.2f} Z'),
        })
        angle += sweep
    return {'total': int(total), 'slices': out}


def overview_report(site, request):
    """Ерөнхий тайлан: income (Орлого), expense (Зарлага), profit and pies.

    Income = orders delivered in the period ("Хүргэлт дууссан" only; taken,
    assigned, pending and cancelled orders are not income).
    Expense = everything added to stock in the period (StockEntry rows:
    deliveries, new products' starting stock, and the stock already on hand
    when this feature was added), at its purchase price.
    """
    T = get_translations(request)
    lang = get_language(request)
    date_from, date_to = _date_range(request)
    start, end = _bounds(date_from, date_to)

    income_rows = (
        _income_items(request).values('product__category__name')
        .annotate(income=Sum(LINE_TOTAL))
    )
    expense_rows = (
        StockEntry.objects.filter(created_at__gte=start, created_at__lt=end)
        .values('product__category__name')
        .annotate(expense=Sum(ExpressionWrapper(
            F('quantity') * F('unit_cost'),
            output_field=DecimalField(max_digits=16, decimal_places=2))))
    )
    by_name = {}
    for key, rows in (('income', income_rows), ('expense', expense_rows)):
        for r in rows:
            name = r['product__category__name']
            label = translate_category_name(name, lang) if name else '—'
            by_name.setdefault(label, {'income': 0, 'expense': 0})[key] += int(r[key] or 0)
    table = [{'name': n, 'income': v['income'], 'expense': v['expense'], 'profit': v['income'] - v['expense']}
             for n, v in by_name.items()]
    table.sort(key=lambda t: (-t['income'], -t['expense'], t['name']))
    income = sum(t['income'] for t in table)
    expense = sum(t['expense'] for t in table)

    def top(pairs):
        pairs = sorted(pairs, key=lambda p: -p[1])
        if len(pairs) > 8:
            pairs = pairs[:7] + [(T['admin_overview_other'], sum(v for _l, v in pairs[7:]))]
        return pairs

    context = {
        **site.each_context(request),
        'title': T['admin_report_overview'],
        'report_title': T['admin_report_overview'],
        'date_from': date_from.isoformat(), 'date_to': date_to.isoformat(),
        'income': income, 'expense': expense, 'profit': income - expense,
        'pie_income': _pie(top([(t['name'], t['income']) for t in table])),
        'pie_expense': _pie(top([(t['name'], t['expense']) for t in table])),
        'pie_split': _pie([(T['admin_revenue'], income), (T['admin_overview_expense'], expense)]),
        'table': table,
    }
    return TemplateResponse(request, 'admin/report_overview.html', context)


# (url name, path, translation key, view). The first entry is also the
# "Reports" group's own link. Order here = order in the sidebar.
REPORTS = [
    ('report_overview', 'reports/overview/', 'admin_report_overview', overview_report),
    ('report_inventory', 'reports/inventory/', 'admin_report_inventory', inventory_report),
    ('report_orders', 'reports/orders/', 'admin_report_orders', orders_report),
    ('report_customers', 'reports/customers/', 'admin_report_customers', customers_report),
]

# (url name, path, view) - detail popups; not shown in the sidebar.
DETAIL_VIEWS = [
    ('report_product_detail', 'reports/product/<int:pk>/', product_detail),
    ('report_customer_detail', 'reports/customer/<int:pk>/', customer_detail),
]