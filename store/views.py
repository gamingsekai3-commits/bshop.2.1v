import json
from decimal import Decimal, InvalidOperation
from email.mime import message
from urllib import request

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import HttpResponseRedirect, JsonResponse
from django.db.models import Case, IntegerField, Q, Value, When
import urllib

from cart.cart import Cart
from .pager import _url as _query_url, paginate_rows
from .stock_rules import low_q, ok_q, out_q
from .models import HERO_MAX_SLIDES, Category, HeroSlide, Product, Customer, Employee, SearchHistory, StockEntry
from .pricing import js_config as markup_config, markup_percent, selling_price
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django import forms
from .forms import RegisterForm, ProductForm, EmployeeForm, CustomerProfileForm, EmployeeProfileForm
from .translations import t, get_language, get_translations, AVAILABLE_LANGUAGES, COOKIE_NAME
from .workspaces import get_workspaces, is_work_user, landing_redirect, workspace_url
from .search_utils import search_products, correct_query, suggest
from .sorting import apply_sort_and_period
from django.contrib.admin.sites import site as admin_site


# Reused on every staff-only view below (employee list, add employee).
# Not signed in -> Work Web login (staff can't use the customer login).
staff_required = user_passes_test(lambda u: u.is_authenticated and u.is_staff, login_url='work_login')

def _hero_slides(request):
    """Slides for the home page slider: exactly the ones the admin made
    (Customize -> Home page slider), at most HERO_MAX_SLIDES. No slides = no slider."""
    default_button = get_translations(request)['product_detail_btn']
    rows = (HeroSlide.objects
            .filter(is_active=True, product__is_active=True)
            .exclude(image='')
            .select_related('product')
            .order_by('sort_order', 'id')[:HERO_MAX_SLIDES])
    return [{
        'product': r.product,
        'image_url': r.image.url,
        'button': r.button_text or default_button,
        'position': r.button_position,
    } for r in rows]


def home(request):
    # Only products whose is_active flag is on. Switching a product off in
    # the admin hides it here without deleting it from the database.
    products = apply_sort_and_period(Product.active.all(), request)
    return render(request, 'home.html', {
        'products': products,
        'hero_slides': _hero_slides(request),
    })

def about(request):
    return render(request, 'about.html', {})

def products_detail(request, pk):
    # get_object_or_404 on the "active" manager: a switched-off product gives
    # a normal 404 rather than a crash or a page nobody should be buying from.
    product = get_object_or_404(Product.active, id=pk)
    return render(request, 'product_detail.html', {'product': product})

def category(request, catname):
    catname = urllib.parse.unquote(catname).replace('-', ' ')
    try:
        cat = Category.active.get(name=catname)
        products = apply_sort_and_period(Product.active.filter(category=cat), request)
        product_form = ProductForm(initial={'category': cat}, lang=get_language(request))
        return render(request, 'category.html', {
            'products': products,
            'category': cat,
            'product_form': product_form,
        })
    except:
        messages.success(request, t(request, 'msg_category_not_found'))
        return redirect('home')

def add_product(request, catname):
    if not request.user.is_authenticated or not request.user.is_staff:
        messages.error(request, t(request, 'msg_admin_only_add_product'))
        return redirect('category', catname=catname)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, lang=get_language(request))
        if form.is_valid():
            form.save()
            messages.success(request, t(request, 'msg_product_added'))
        else:
            messages.error(request, t(request, 'msg_form_invalid'))
    return redirect('category', catname=catname)

def login_user(request):
    """Customer login. Admins, drivers and employees are refused here and sent
    to the Work Web login instead - they only sign in at /work/."""
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if is_work_user(user):
                # Correct password, wrong door: do NOT sign them in.
                messages.error(request, t(request, 'msg_work_only'))
                return redirect('login')
            login(request, user)
            messages.success(request, t(request, 'msg_login_success'))
            return landing_redirect(user)      # customers -> shop home
        else:
            messages.error(request, t(request, 'msg_login_failed'))
            return redirect('login')
    else:
        return render(request, 'login.html', {})


def work_login(request):
    """Work Web login: the only way in for admins, drivers and employees.

    One sign-in opens every site the person's positions allow: one site -> straight
    in, two or more -> the "which site?" chooser. Customers are refused here too
    (they use the normal shop login).
    """
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, t(request, 'msg_login_failed'))
            return redirect(_work_login_url(request.POST.get('next', '')))
        if not is_work_user(user):
            # A customer account: don't sign it in on the staff side.
            messages.error(request, t(request, 'msg_customer_only'))
            return redirect(_work_login_url(request.POST.get('next', '')))
        login(request, user)
        messages.success(request, t(request, 'msg_login_success'))
        next_url = request.POST.get('next', '')
        if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return redirect(next_url)          # deep link, e.g. /admin/store/product/
        return landing_redirect(user)

    # Already signed in with a site to open: skip the form. `next` is ignored on
    # purpose here - honouring it could bounce someone between a site they have
    # no access to and this page forever.
    if get_workspaces(request.user):
        return landing_redirect(request.user)
    return render(request, 'work_login.html', {'next': request.GET.get('next', '')})


def _work_login_url(next_url=''):
    """/work/ plus a safe ?next= so a failed attempt keeps the deep link."""
    from urllib.parse import urlencode
    from django.urls import reverse
    url = reverse('work_login')
    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        url += '?' + urlencode({'next': next_url})
    return url


@login_required(login_url='work_login')
def choose_workspace(request):
    """Shown to someone who can open more than one site (e.g. holds both the
    Admin and Хүргэгч positions). One site -> straight in; none -> shop home."""
    spaces = get_workspaces(request.user)
    if not spaces:
        return redirect('home')
    if len(spaces) == 1:
        return redirect(workspace_url(spaces[0]))
    return render(request, 'choose_workspace.html', {
        'workspaces': [{'key': w.key, 'label': w.label, 'url': workspace_url(w)} for w in spaces],
    })


def logout_user(request):
    logout(request)
    messages.success(request, t(request, 'msg_logout_success'))
    return redirect('home')

def register_user(request):
    lang = get_language(request)
    if request.method == 'POST':
        form = RegisterForm(request.POST, lang=lang)
        if form.is_valid():
            form.save()
            messages.success(request, t(request, 'msg_register_success'))
            return redirect('login')
        else:
            messages.error(request, t(request, 'msg_register_failed'))
    else:
        form = RegisterForm(lang=lang)
    return render(request, 'register.html', {'form': form})

@login_required
def profile(request):
    """Lets any logged-in user (customer or employee) edit their own
    private info. Which form/model is used depends on is_staff, but either
    way a user can only ever edit their own row, never anyone else's."""
    lang = get_language(request)
    if request.user.is_staff:
        instance, _ = Employee.objects.get_or_create(user=request.user)
        form_class = EmployeeProfileForm
    else:
        instance, _ = Customer.objects.get_or_create(user=request.user)
        form_class = CustomerProfileForm

    if request.method == 'POST':
        form = form_class(request.POST, instance=instance, lang=lang)
        if form.is_valid():
            form.save()
            messages.success(request, t(request, 'msg_profile_updated'))
            return redirect('profile')
        else:
            messages.error(request, t(request, 'msg_form_invalid'))
    else:
        form = form_class(instance=instance, lang=lang)
    positions = instance.position_list if request.user.is_staff else []
    return render(request, 'profile.html', {'form': form, 'positions': positions})


@staff_required
def employees(request):
    employees = User.objects.filter(Q(is_staff=True) | Q(driver_profile__isnull=False)).select_related('employee_profile').prefetch_related('employee_profile__positions').order_by('username')
    return render(request, 'employees.html', {'employees': employees})


@staff_required
def add_employee(request):
    lang = get_language(request)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, lang=lang)
        if form.is_valid():
            form.save()
            messages.success(request, t(request, 'msg_employee_added'))
            return redirect('employees')
        else:
            messages.error(request, t(request, 'msg_form_invalid'))
    else:
        form = EmployeeForm(lang=lang)
    return render(request, 'add_employee.html', {'form': form})


from django.db.models import Q
from .models import Category, Product, Customer, Employee, SearchHistory

def search(request):
    """Runs the search and records it in the history.

    The history *display* (the dropdown in the navbar) is no longer built here:
    it comes from store.context_processors.search_dropdown, so it is available
    on every page and not just on this one.
    """
    search_value = request.GET.get('searched', '').strip()

    result = Product.active.none()
    corrected_query = None

    if search_value:
        result = search_products(search_value)

        # Nothing found: try a spelling-corrected version ("sedna" -> "sedan")
        # and, if that finds something, show it with a "showing results for" note.
        if not result.exists():
            candidate = correct_query(search_value)
            if candidate and candidate != search_value.lower():
                corrected_result = search_products(candidate)
                if corrected_result.exists():
                    result = corrected_result
                    corrected_query = candidate

        if request.user.is_authenticated:
            # Same query typed again: drop the old row so it moves to the top.
            SearchHistory.objects.filter(
                user=request.user,
                query__iexact=search_value
            ).delete()

            SearchHistory.objects.create(
                user=request.user,
                query=search_value
            )

            # Keep only the 10 newest.
            old_ids = list(
                SearchHistory.objects.filter(user=request.user)
                .order_by('-created_at')
                .values_list('id', flat=True)[10:]
            )
            if old_ids:
                SearchHistory.objects.filter(id__in=old_ids).delete()

        else:
            history = [
                item for item in request.session.get('search_history', [])
                if item.lower() != search_value.lower()
            ]
            history.insert(0, search_value)

            request.session['search_history'] = history[:10]
            request.session.modified = True

        if not result.exists():
            messages.success(
                request,
                t(request, 'msg_search_no_results')
            )

        result = apply_sort_and_period(result, request)

    return render(request, 'search.html', {
        'result': result,
        'search_value': search_value,
        'corrected_query': corrected_query,
    })


def search_suggest(request):
    """JSON for the live "as you type" suggestions in the navbar search box.
    Read-only: typing here does NOT touch the search history (only an actual
    search does)."""
    query = request.GET.get('q', '').strip()[:100]
    if not query:
        return JsonResponse({'did_you_mean': None, 'categories': [], 'products': []})
    return JsonResponse(suggest(query))

def delete_search_history(request):
    if request.method != 'POST':
        return JsonResponse({'success': False}, status=405)

    query = request.POST.get('query', '').strip()

    if request.user.is_authenticated:
        if query:
            SearchHistory.objects.filter(
                user=request.user,
                query=query
            ).delete()
    else:
        history = request.session.get('search_history', [])

        history = [
            item for item in history
            if item != query
        ]

        request.session['search_history'] = history
        request.session.modified = True

    return JsonResponse({'success': True})


def clear_search_history(request):
    if request.method != 'POST':
        return JsonResponse({'success': False}, status=405)

    if request.user.is_authenticated:
        SearchHistory.objects.filter(
            user=request.user
        ).delete()
    else:
        request.session['search_history'] = []
        request.session.modified = True

    return JsonResponse({'success': True})


# Columns of the Stock page that can be sorted by clicking the header. The
# order is applied to the whole queryset before it is paginated, so it
# spans every page, not just the 10 rows on screen.
STOCK_SORT_FIELDS = {
    'name': ('name',),
    'category': ('category__name', 'name'),
    'sku': ('id',),
    'price': ('price', 'name'),
    'stock': ('stock', 'name'),
    'status': ('_stock_rank', 'name'),          # out -> low -> ok
}


def _apply_stock_sort(request, products):
    """Return (ordered queryset, {column: {'mark': ..., 'url': ...}}).
    Click cycle per column: ascending -> descending -> off. Unknown values
    of ?sort= / ?dir= are ignored."""
    sort = request.GET.get('sort')
    direction = request.GET.get('dir')
    if sort not in STOCK_SORT_FIELDS or direction not in ('asc', 'desc'):
        sort = direction = None

    columns = {}
    for key in STOCK_SORT_FIELDS:
        if key == sort and direction == 'asc':
            columns[key] = {'mark': '\u25B2', 'url': _query_url(request, sort=key, dir='desc', p=None)}
        elif key == sort:
            columns[key] = {'mark': '\u25BC', 'url': _query_url(request, sort=None, dir=None, p=None)}
        else:
            columns[key] = {'mark': '\u21C5', 'url': _query_url(request, sort=key, dir='asc', p=None)}

    if sort is None:
        return products.order_by('name'), columns
    if sort == 'status':
        products = products.annotate(_stock_rank=Case(
            When(out_q(), then=Value(0)), When(low_q(), then=Value(1)),
            default=Value(2), output_field=IntegerField()))
    order = [('-' if direction == 'desc' else '') + f for f in STOCK_SORT_FIELDS[sort]]
    return products.order_by(*order), columns


@staff_member_required
def stock(request):
    products = Product.objects.select_related('category').all().order_by('name')
    search_value = request.GET.get('q', '').strip()
    status = request.GET.get('status', 'all')

    if search_value:
        products = products.filter(name__icontains=search_value)

    # "Low" depends on the product's price - see store/stock_rules.py.
    if status == 'out':
        products = products.filter(out_q())
    elif status == 'low':
        products = products.filter(low_q())
    elif status == 'ok':
        products = products.filter(ok_q())

    all_products = Product.objects.all()
    total_products = all_products.count()
    total_stock_units = sum(p.stock for p in all_products)
    in_stock_count = all_products.filter(ok_q()).count()
    low_stock_count = all_products.filter(low_q()).count()
    out_of_stock_count = all_products.filter(out_q()).count()

    total_asset_value = sum(
        ((p.sale_price if p.is_sale and p.sale_price > 0 else p.price) * p.stock)
        for p in all_products
    )

    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        try:
            quantity = int(request.POST.get('quantity', 0))
        except (TypeError, ValueError):
            quantity = 0

        if quantity < 1:
            messages.error(request, 'Нөөцөд нэмэх тоо 1-ээс их байх ёстой.')
        else:
            product = Product.objects.filter(id=product_id).first()
            if product:
                # Purchase price per unit: what was typed in the popup, else
                # the product's saved cost price. Whatever is typed becomes
                # the new default for the next delivery.
                try:
                    unit_cost = Decimal(request.POST.get('unit_cost', '').strip() or product.cost_price)
                    if unit_cost < 0:
                        raise ValueError
                except (InvalidOperation, ValueError):
                    unit_cost = product.cost_price
                product.stock += quantity
                product.cost_price = unit_cost
                fields = ['stock', 'cost_price']
                # Selling price = purchase price + 20-30 % (cheaper goods get
                # the bigger mark-up, see store/pricing.py). No cost -> no
                # automatic price, the old one stays.
                new_price = selling_price(unit_cost)
                if new_price is not None:
                    product.price = new_price
                    fields.append('price')
                product.save(update_fields=fields)
                # Every addition is an expense: quantity x unit_cost.
                StockEntry.objects.create(
                    product=product, name=product.name, quantity=quantity, unit_cost=unit_cost)
                msg = f'{product.name} барааны үлдэгдэл {quantity} ширхэгээр нэмэгдлээ.'
                if new_price is not None:
                    msg += f' Борлуулах үнэ: {new_price:,.0f}₮ (+{markup_percent(unit_cost):.1f}%).'
                messages.success(request, msg)
            else:
                messages.error(request, 'Бараа олдсонгүй.')
        return redirect(request.get_full_path())

    # `stock.html` extends admin/base_site.html, which (like every real admin
    # page) expects `available_apps`, `has_permission`, `is_nav_sidebar_enabled`,
    # `site_url`, etc. Django's own admin views get these for free because
    # they go through AdminSite.each_context(). This view is a plain function
    # view, so without merging that in, the sidebar and the profile menu had
    # nothing to render and silently disappeared on this one page.
    context = admin_site.each_context(request)
    # One page of rows (?p=, ?per_page=); the summary cards above are counted
    # from all products, so they do not change with the page.
    products, sort_columns = _apply_stock_sort(request, products)
    products, pager = paginate_rows(request, products)
    context.update({
        'pager': pager,
        'sort_columns': sort_columns,
        'products': products,
        'search_value': search_value,
        'status': status,
        'total_products': total_products,
        'total_stock_units': total_stock_units,
        'in_stock_count': in_stock_count,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'total_asset_value': total_asset_value,
        'markup_config_json': json.dumps(markup_config()),   # constants only, no user input
    })
    return render(request, 'admin/stock.html', context)


def set_language(request, lang_code):
    """Sets the visitor's preferred UI language in a cookie and redirects
    back to whatever page they were on."""
    valid_codes = [code for code, _ in AVAILABLE_LANGUAGES]
    if lang_code not in valid_codes:
        lang_code = 'mn'
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or '/'
    response = HttpResponseRedirect(next_url)
    response.set_cookie(COOKIE_NAME, lang_code, max_age=60 * 60 * 24 * 365)
    return response