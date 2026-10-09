"""The pager under every admin list (products, categories, employees, ...).

Used from templates/admin/change_list.html in place of Django's own
{% pagination cl %} tag. It is written as a takes_context tag (Django's is
not) so that it can read LANG and show the label in the visitor's language.
"""
from django import template

register = template.Library()


def _url(cl, page=None, per_page=None):
    """Query string for a page link. Everything already in the URL (search,
    filters, sort order, page size) is kept; page 1 simply drops ?p=."""
    params = {'p': page if page and page > 1 else None}
    if per_page is not None:
        params['per_page'] = per_page
    return cl.get_query_string(params)


@register.inclusion_tag('admin/bshop_pager.html', takes_context=True)
def bshop_pager(context, cl):
    total = cl.result_count
    sizes_available = getattr(cl, 'page_sizes', None)      # only BshopChangeList has it

    # The pager is always shown, even for a short list (then it is just
    # "‹ 1 ›" with a disabled arrow on each side, the row count and the
    # rows-per-page dropdown).
    show = True
    multi_page = bool(cl.multi_page) and not (cl.show_all and cl.can_show_all)

    pages, prev_url, next_url, sizes = [], None, None, []
    per_page = cl.paginator.per_page
    if multi_page:
        num_pages = cl.paginator.num_pages
        current = cl.page_num
        try:
            page_range = list(cl.paginator.get_elided_page_range(
                current, on_each_side=2, on_ends=1))
        except Exception:                        # page number out of range
            page_range = []
        for i in page_range:
            if i == cl.paginator.ELLIPSIS:
                pages.append({'kind': 'gap'})
            elif i == current:
                pages.append({'kind': 'current', 'label': i})
            else:
                pages.append({'kind': 'link', 'label': i, 'url': _url(cl, i)})
        if current > 1:
            prev_url = _url(cl, current - 1)
        if current < num_pages:
            next_url = _url(cl, current + 1)
        first = (current - 1) * per_page + 1
        last = min(current * per_page, total)
    else:
        pages = [{'kind': 'current', 'label': 1}]
        first, last = (1 if total else 0), total
    for n in (sizes_available or ()):
        sizes.append({'value': n, 'url': _url(cl, None, n), 'selected': n == cl.list_per_page})

    lang = context.get('LANG') or 'mn'
    if lang == 'en':
        text = f'Results: {first} - {last} of {total}'
        labels = {'prev': 'Previous page', 'next': 'Next page', 'per_page': 'Rows per page'}
    else:
        text = f'Үр дүн: {first} - {last} / {total}'
        labels = {'prev': 'Өмнөх хуудас', 'next': 'Дараагийн хуудас', 'per_page': 'Нэг хуудсанд харуулах мөр'}

    return {
        'show': show, 'multi_page': True, 'pages': pages,
        'prev_url': prev_url, 'next_url': next_url,
        'sizes': sizes, 'text': text, 'labels': labels,
    }


@register.inclusion_tag('admin/bshop_pager.html')
def bshop_report_pager(pager):
    """Pager under a report table; `pager` comes from store.pager.paginate_rows."""
    return pager or {'show': False}
