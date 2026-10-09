"""Pager for the report tables (Reports menu), same look as the model lists.

Unlike the model lists, a report builds its whole table in Python first, so
the rows are simply sliced here. Totals/footers and the summary cards are
calculated from ALL rows before this runs, so they never change with the page.
"""
from django.core.paginator import EmptyPage, Paginator

from .translations import get_language

PAGE_SIZES = (10, 25, 50, 100)
DEFAULT_PAGE_SIZE = 10


def _url(request, **changes):
    """Current URL's query string (date range, ...) with some params changed."""
    params = request.GET.copy()
    for key, value in changes.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    return '?' + params.urlencode() if params else '?'


def paginate_rows(request, rows):
    """Return (rows_for_this_page, context_for_bshop_pager.html)."""
    try:
        per_page = int(request.GET.get('per_page', ''))
    except ValueError:
        per_page = DEFAULT_PAGE_SIZE
    if per_page not in PAGE_SIZES:
        per_page = DEFAULT_PAGE_SIZE

    paginator = Paginator(rows, per_page)
    try:
        number = int(request.GET.get('p', 1))
        page = paginator.page(number)
    except (ValueError, EmptyPage):
        page = paginator.page(1)
    number, total = page.number, paginator.count

    pages = []
    for i in paginator.get_elided_page_range(number, on_each_side=2, on_ends=1):
        if i == paginator.ELLIPSIS:
            pages.append({'kind': 'gap'})
        elif i == number:
            pages.append({'kind': 'current', 'label': i})
        else:
            pages.append({'kind': 'link', 'label': i,
                          'url': _url(request, p=i if i > 1 else None)})

    first = (number - 1) * per_page + 1 if total else 0
    last = min(number * per_page, total)
    if get_language(request) == 'en':
        text = f'Results: {first} - {last} of {total}'
        labels = {'prev': 'Previous page', 'next': 'Next page', 'per_page': 'Rows per page'}
    else:
        text = f'Үр дүн: {first} - {last} / {total}'
        labels = {'prev': 'Өмнөх хуудас', 'next': 'Дараагийн хуудас', 'per_page': 'Нэг хуудсанд харуулах мөр'}

    ctx = {
        'show': True, 'multi_page': True, 'pages': pages,
        'single_page': paginator.num_pages <= 1,
        'prev_url': _url(request, p=number - 1 if number > 2 else None) if number > 1 else None,
        'next_url': _url(request, p=number + 1) if number < paginator.num_pages else None,
        'sizes': [{'value': n, 'url': _url(request, p=None, per_page=n), 'selected': n == per_page}
                  for n in PAGE_SIZES],
        'text': text, 'labels': labels,
    }
    return list(page.object_list), ctx
