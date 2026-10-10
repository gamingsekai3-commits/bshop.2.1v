from django import forms
from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import PermissionDenied
from django.db.models import Case, DecimalField, ExpressionWrapper, F, IntegerField, Max, Min, Q, When
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.views.decorators.clickjacking import xframe_options_sameorigin
from .forms import POSITION_CHOICES, ProductForm, position_choices_with

from .models import (HERO_MAX_SLIDES, HERO_MAX_UPLOAD_MB, HERO_MIN_SIZE, Category, Customer, Employee,
                     HeroSlide, Product, ProductOption, StockEntry)
from .pricing import margin_percent, selling_price
from .stock_rules import low_q, out_q
from .translations import get_language, get_translations, lazy_t, translate_category_name, translate_position


# Rows-per-page choices offered in the pager's dropdown (?per_page=N).
PAGE_SIZES = (10, 25, 50, 100)
DEFAULT_PAGE_SIZE = 10


# --------------------------------------------------------------------------
# Column funnels on model lists (same idea and same URL style as Reports)
# --------------------------------------------------------------------------
# Each admin may declare   column_filters = {<list_display name>: (mode, expr[, labeler])}
#   mode    LIST  - tick-list of the column's values        (name, category, status ...)
#           COUNT - fixed buckets 0-9 / 10-19 / 20-29 / 30+  (stock)
#           MONEY - intervals built from the column's lowest / highest value (price)
#   expr    the database field / annotation the column is filtered on
#   labeler optional  fn(raw_value, T, en) -> text shown in the tick-list
# The funnel filters on the SERVER, over ALL pages: ?f_<column>=<value> (repeated for
# several values). Options come from the whole list (search + sidebar filter applied,
# other funnels not), so ticking one box never makes the other boxes disappear.
# static/admin/js/table-filter.js reads them from <script id="bshop-fopts"> (change_list.html).
LIST, COUNT, MONEY = 'list', 'count', 'money'
COLUMN_PARAM_PREFIX = 'f_'


def _lab_active(raw, T, en):
    return T['admin_active'] if raw else T['admin_inactive']


def _lab_yes_no(raw, T, en):
    return T['admin_yes'] if raw else T['admin_no']


def _lab_category(raw, T, en):
    return translate_category_name(raw, 'en' if en else 'mn')


def _lab_position(raw, T, en):
    return translate_position(raw, 'en' if en else 'mn')


def _lab_stock_state(raw, T, en):
    key = {0: 'admin_out_of_stock', 1: 'admin_low_stock_status'}.get(raw, 'admin_in_stock')
    return T[key]


def _bucket_q(expr, k, edges):
    """Q for bucket k of `edges` (same rule as Reports: upper edge inclusive, the
    first bucket open below, the last open above)."""
    q = Q()
    if k > 0:
        q &= Q(**{f'{expr}__gt': edges[k]})
    if k < len(edges) - 2:
        q &= Q(**{f'{expr}__lte': edges[k + 1]})
    return q


class BshopChangeList(ChangeList):
    """Django's ChangeList, plus a user-chosen page size and Reports-style column funnels.

    The pager (templates/admin/pagination.html) links to ?per_page=25 etc.
    Two things are needed for that to work:
      * per_page must not be treated as a database filter, otherwise Django
        redirects to "?e=1" because no field is called "per_page";
      * list_per_page must be changed before the paginator is built. It is
        set on this per-request object, not on the shared ModelAdmin, so
        two people using different page sizes cannot affect each other.
    The same goes for the ?f_<column>= funnel parameters (see above).
    """
    page_sizes = PAGE_SIZES
    column_filter_info = None      # {column: {param, kind, options, values, selected}} for the template

    def _column_specs(self):
        return getattr(self.model_admin, 'column_filters', None) or {}

    def get_filters_params(self, params=None):
        lookup_params = super().get_filters_params(params)
        lookup_params.pop('per_page', None)
        for name in self._column_specs():
            lookup_params.pop(COLUMN_PARAM_PREFIX + name, None)
        return lookup_params

    def get_ordering(self, request, queryset):
        # One sort column at a time, like Reports. Django would keep stacking columns
        # (?o=3.1.2 - "sort by 3, then 1, then 2"); the column just clicked always comes
        # first in that list, so keep only it. self.params feeds the header marks and
        # links too, so they agree with what is really sorted.
        order = self.params.get('o')
        if order and '.' in order:
            self.params['o'] = order.split('.')[0]
        return super().get_ordering(request, queryset)

    def get_queryset(self, request, *args, **kwargs):
        qs = super().get_queryset(request, *args, **kwargs)
        return self._apply_column_filters(request, qs)

    def _field_choices(self, expr):
        """{stored value: label} when `expr` is a plain model field with choices."""
        try:
            return {k: str(v) for k, v in self.model._meta.get_field(expr).flatchoices}
        except Exception:
            return {}

    def _apply_column_filters(self, request, qs):
        specs = self._column_specs()
        self.column_filter_info = {}
        if not specs:
            return qs
        from .reports import COUNT_EDGES, _money_edges      # lazy: reports imports this app's models
        T, en = get_translations(request), get_language(request) == 'en'
        tests = []
        for name in self.list_display:
            spec = specs.get(name)
            if not spec:
                continue
            mode, expr = spec[0], spec[1]
            labeler = spec[2] if len(spec) > 2 else None
            param = COLUMN_PARAM_PREFIX + name
            chosen = request.GET.getlist(param)

            if mode == LIST:
                choices = self._field_choices(expr)
                raws = list(qs.order_by().values_list(expr, flat=True).distinct())
                lookup, labels = {}, {}
                for raw in raws:
                    value = str(raw)
                    if value in lookup:
                        continue
                    lookup[value] = raw
                    if labeler:
                        text = str(labeler(raw, T, en))
                    elif raw is None or raw == '':
                        text = T['admin_empty']
                    else:
                        text = choices.get(raw, str(raw))
                    labels[value] = text
                values = sorted(lookup, key=lambda v: labels[v].casefold())
                options = [labels[v] for v in values]
                kind = 'list'
                selected = [v for v in chosen if v in lookup]
                if selected and len(selected) < len(values):
                    picked = [lookup[v] for v in selected]
                    q = Q()
                    present = [r for r in picked if r is not None]
                    if present:
                        q |= Q(**{f'{expr}__in': present})
                    if len(present) != len(picked):
                        q |= Q(**{f'{expr}__isnull': True})
                    tests.append(q)
            else:
                if mode == COUNT:
                    edges = [None, *COUNT_EDGES, None]
                    options = ['0 – 9', '10 – 19', '20 – 29', '30 and up' if en else '30-с дээш']
                else:       # MONEY
                    agg = qs.order_by().aggregate(lo=Min(expr), hi=Max(expr))
                    if agg['lo'] is None:
                        continue
                    edges = _money_edges([float(agg['lo']), float(agg['hi'])])
                    if len(edges) < 2:
                        continue
                    if edges[0] == edges[-1]:
                        options = [f'{edges[0]:,.0f}']
                    else:
                        options = [f'{edges[k]:,.0f} – {edges[k + 1]:,.0f}' for k in range(len(edges) - 1)]
                values = [str(n) for n in range(len(options))]
                kind = 'range'
                selected = [v for v in chosen if v in values]
                if selected and len(selected) < len(values):
                    q = Q()
                    for v in selected:
                        q |= _bucket_q(expr, int(v), edges)
                    tests.append(q)

            self.column_filter_info[name] = {
                'param': param, 'kind': kind, 'options': options, 'values': values, 'selected': selected,
            }
        for q in tests:
            qs = qs.filter(q)
        return qs

    def get_results(self, request):
        try:
            size = int(request.GET.get('per_page', ''))
        except ValueError:
            size = None
        if size in PAGE_SIZES:
            self.list_per_page = size
        super().get_results(request)
        # Optional hook: a ModelAdmin may load per-page extras ONCE here (instead of one
        # query per row while the rows are drawn), e.g. OrderAdmin's driver dropdown options.
        hook = getattr(self.model_admin, 'prepare_rows', None)
        if hook:
            hook(request, list(self.result_list))


class PopupFriendlyAdmin:
    """Lets this model's add/change view render inside our own edit popup
    (see templates/admin/change_list.html + static/admin/js/popup-edit.js),
    without loosening X-Frame-Options anywhere else in the site.

    Django's default X_FRAME_OPTIONS is 'DENY', which stops the change page
    from being drawn inside our popup's <iframe> - the browser just shows a
    blank box. This decorator scopes the exemption to 'SAMEORIGIN' (our own
    site only) for this one view, instead of changing the setting globally.
    """

    @method_decorator(xframe_options_sameorigin)
    def changeform_view(self, request, *args, **kwargs):
        return super().changeform_view(request, *args, **kwargs)

    # The delete *confirmation* page (…/<id>/delete/) is rendered by
    # delete_view, not changeform_view - without this it would be blank
    # when opened from the "Delete" button inside the row-edit popup.
    @method_decorator(xframe_options_sameorigin)
    def delete_view(self, request, *args, **kwargs):
        return super().delete_view(request, *args, **kwargs)


class ActiveStatusAdmin(PopupFriendlyAdmin, admin.ModelAdmin):
    """Shared behaviour for every table that uses the is_active flag.

    Instead of deleting a row you switch it off: the record stays in the
    database (so old orders, totals and admin history keep making sense) but
    it stops showing up on the storefront. Each list page gets an Active /
    Inactive badge, a filter, and two bulk actions in the Action dropdown.
    """

    actions = ['make_active', 'make_inactive']

    # Pager: 10 rows per page by default; the dropdown under the table lets
    # the user switch to 25 / 50 / 100 (see BshopChangeList above).
    list_per_page = DEFAULT_PAGE_SIZE

    # Column funnels (see the comment above BshopChangeList). Subclasses extend this.
    column_filters = {
        'status_badge': (LIST, 'is_active', _lab_active),
        'is_active': (LIST, 'is_active', _lab_active),
    }

    def get_changelist(self, request, **kwargs):
        return BshopChangeList

    # Status columns can't be sorted: the ones that show a status (Төлөв /
    # Идэвхтэй эсэх / Үлдэгдлийн төлөв). They keep their column funnel
    # (filter), only the sort arrow / ?o= is switched off.
    unsortable_columns = ('status', 'status_badge', 'is_active', 'stock_status')

    def get_sortable_by(self, request):
        columns = self.sortable_by if self.sortable_by is not None else self.get_list_display(request)
        return [c for c in columns if c not in self.unsortable_columns]

    @admin.display(description=lazy_t('admin_status'), ordering='is_active')
    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color:#27ae60;font-weight:bold;">&#9679; {}</span>',
                str(lazy_t('admin_active')),
            )
        return format_html(
            '<span style="color:#c0392b;font-weight:bold;">&#9679; {}</span>',
            str(lazy_t('admin_inactive')),
        )

    def _set_active(self, request, queryset, value):
        # Looped rather than queryset.update() so each model's save() still
        # runs - Employee/Customer use it to switch the login on or off too.
        changed = 0
        for obj in queryset:
            if obj.is_active != value:
                obj.is_active = value
                obj.save()
                changed += 1
        key = 'admin_msg_activated' if value else 'admin_msg_deactivated'
        self.message_user(request, f"{changed} - {lazy_t(key)}")

    @admin.action(description=lazy_t('admin_action_activate'))
    def make_active(self, request, queryset):
        self._set_active(request, queryset, True)

    @admin.action(description=lazy_t('admin_action_deactivate'))
    def make_inactive(self, request, queryset):
        self._set_active(request, queryset, False)

    # ------------------------------------------------------------------
    # Delete -> soft delete
    # ------------------------------------------------------------------
    # Every model here already has an is_active flag for exactly this: the
    # row (and anything that points at it - orders, admin log entries,
    # other tables' foreign keys) stays in the database, it just stops
    # showing up on the storefront. So "Delete" - the red link/button on
    # the change form, its confirmation page, and the "Delete selected"
    # bulk action - now flips is_active off instead of calling .delete().
    #
    # Note: Django's delete confirmation page still lists related objects
    # that a real delete *would* cascade to (e.g. a category's products),
    # since that list is generated before delete_model/delete_queryset
    # ever runs. Nothing actually gets deleted - the wording is just
    # slightly misleading in that one screen.

    def delete_model(self, request, obj):
        if obj.is_active:
            obj.is_active = False
            obj.save()

    def delete_queryset(self, request, queryset):
        # Looped, not queryset.update(), so each model's own save()
        # override still runs (Employee/Customer use it to also switch
        # off the linked auth User's login).
        for obj in queryset:
            if obj.is_active:
                obj.is_active = False
                obj.save()


@admin.register(Category)
class CategoryAdmin(ActiveStatusAdmin):
    # A method (not the 'name' field itself) so the shown name can follow the site language.
    list_display = ('name_display', 'status_badge', 'is_active')
    list_editable = ('is_active',)
    list_filter = ('is_active',)
    search_fields = ('name',)
    column_filters = {**ActiveStatusAdmin.column_filters, 'name_display': (LIST, 'name', _lab_category)}

    @admin.display(description=lazy_t('admin_col_name'), ordering='name')
    def name_display(self, obj):
        return str(obj)       # Category.__str__ translates to the current language


class EmployeeAdminForm(forms.ModelForm):
    position = forms.ChoiceField(choices=POSITION_CHOICES[1:], label=lazy_t('f_position'))

    class Meta:
        model = Employee
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['position'].choices = position_choices_with(getattr(self.instance, 'position', ''))


@admin.register(Employee)
class EmployeeAdmin(ActiveStatusAdmin):
    form = EmployeeAdminForm
    list_display = ('username', 'position_display', 'phone', 'hired_at', 'status_badge', 'is_active')
    sortable_by = ()    # no sorting on any column of the employee table
    list_editable = ('is_active',)
    list_filter = ('is_active',)
    search_fields = ('user__username', 'user__email', 'position')
    column_filters = {**ActiveStatusAdmin.column_filters, 'username': (LIST, 'user__username'),
                      'position_display': (LIST, 'position', _lab_position), 'phone': (LIST, 'phone')}

    @admin.display(description=lazy_t('f_position'), ordering='position')
    def position_display(self, obj):
        from .translations import active_language
        return translate_position(obj.position, active_language())

    # A plain 'user' column would sort by the user's id; this sorts by name.
    @admin.display(description=lazy_t('table_username'), ordering='user__username')
    def username(self, obj):
        return obj.user.username


@admin.register(Customer)
class CustomerAdmin(ActiveStatusAdmin):
    list_display = ('username', 'phone', 'address', 'status_badge', 'is_active')
    list_editable = ('is_active',)
    list_filter = ('is_active',)
    search_fields = ('user__username', 'user__email')
    column_filters = {**ActiveStatusAdmin.column_filters, 'username': (LIST, 'user__username'),
                      'phone': (LIST, 'phone'), 'address': (LIST, 'address')}

    @admin.display(description=lazy_t('table_username'), ordering='user__username')
    def username(self, obj):
        return obj.user.username


class ProductOptionInline(admin.TabularInline):
    """Lets you add/edit a product's option choices right on the product's
    own edit page. Add one row per choice: put the group name in
    `option_type` (e.g. "Flavor") and the choice in `value` (e.g.
    "Chocolate"). Adding several rows with the same option_type creates a
    dropdown the customer picks one value from; different option_types
    (e.g. "Flavor" and "Size") show up as separate dropdowns on the
    product page."""
    model = ProductOption
    extra = 2
    fields = ('option_type', 'value', 'is_active')


@admin.register(Product)
class ProductAdmin(ActiveStatusAdmin):
    form = ProductForm

    list_display = (
        'image_thumbnail',
        'name',
        'category_name',
        'price',
        'margin',
        'stock',
        'stock_status',
        'is_sale',
        'rating',
        'status_badge',
        'is_active',
    )

    # Only the name opens the edit popup (static/admin/js/popup-edit.js).
    # The picture is its own link: it opens the read-only detail popup
    # (see detail_view below and static/admin/js/detail-popup.js).
    list_display_links = ('name',)

    list_editable = ('stock', 'is_active')

    # No sort arrow on the Picture / Name / On sale headers (they keep their
    # funnel filter). Added to the shared status columns from ActiveStatusAdmin.
    unsortable_columns = ActiveStatusAdmin.unsortable_columns + (
        'image_thumbnail', 'name', 'is_sale',
    )

    actions = ['make_active', 'make_inactive', 'reprice_from_cost']

    list_filter = (
        'is_active',
        'category',
        'is_sale',
    )

    # Same fields as ProductForm, in the same order - the only addition is
    # image_preview, placed right under the image upload box.
    fields = (
        'name',
        'price',
        'cost_price',
        'category',
        'description',
        'image',
        'image_preview',
        'is_sale',
        'sale_price',
        'stock',
        'rating',
    )
    readonly_fields = ('image_preview',)

    search_fields = ('name',)

    # Funnels in the column headers (server-side, every page). Only Category,
    # Price and Is active keep one - Name, Stock, Stock status, On sale, Rating
    # and Status have no funnel.
    column_filters = {
        'is_active': (LIST, 'is_active', _lab_active),
        'category_name': (LIST, 'category__name', _lab_category),
        'price': (MONEY, 'price'),
    }

    inlines = [ProductOptionInline]

    def save_model(self, request, obj, form, change):
        """Every stock increase is an expense (Reports > Overview), whichever
        screen it comes from: a new product's starting stock, an edit of the
        stock field here or inline in the list, or a change of cost price
        (which re-prices the product's opening-stock entries)."""
        old_stock = 0
        if change:
            old_stock = Product.objects.filter(pk=obj.pk).values_list('stock', flat=True).first() or 0
        super().save_model(request, obj, form, change)
        if not change and obj.stock > 0:
            StockEntry.objects.create(product=obj, name=obj.name, quantity=obj.stock,
                                      unit_cost=obj.cost_price, is_opening=True)
        elif change and obj.stock > old_stock:
            StockEntry.objects.create(product=obj, name=obj.name, quantity=obj.stock - old_stock,
                                      unit_cost=obj.cost_price)
        if change and 'cost_price' in form.changed_data:
            StockEntry.objects.filter(product=obj, is_opening=True).update(unit_cost=obj.cost_price)

        # Selling price = purchase price + 20-30 % (store/pricing.py). Filled in
        # automatically when stock comes in, or when a product has a cost but
        # no price yet - but never over a price the admin typed in this form.
        stock_added = (not change and obj.stock > 0) or (change and obj.stock > old_stock)
        if obj.cost_price > 0 and 'price' not in form.changed_data and (stock_added or obj.price == 0):
            obj.price = selling_price(obj.cost_price)
            obj.save(update_fields=['price'])

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        # Called by the slider's product search box (autocomplete): offer only active products.
        if request.GET.get('model_name') == 'heroslide':
            queryset = queryset.filter(is_active=True).order_by('name', 'pk')   # stable order for paging
        return queryset, use_distinct

    def get_queryset(self, request):
        """Adds the two computed columns the list can be sorted by (the
        status and the mark-up are not database columns)."""
        return super().get_queryset(request).annotate(
            sort_state=Case(When(out_q(), then=0), When(low_q(), then=1), default=2,
                            output_field=IntegerField()),
            margin_sort=Case(
                When(cost_price__gt=0, then=ExpressionWrapper(
                    (F('price') - F('cost_price')) * 100 / F('cost_price'),
                    output_field=DecimalField(max_digits=14, decimal_places=4))),
                default=None, output_field=DecimalField(max_digits=14, decimal_places=4)),
        )

    @admin.display(description=lazy_t('admin_col_category'), ordering='category__name')
    def category_name(self, obj):
        return str(obj.category)      # Category.__str__ translates to the current language

    @admin.action(description=lazy_t('admin_action_reprice'))
    def reprice_from_cost(self, request, queryset):
        """Set price = cost + mark-up for the selected products (those with a
        cost price). For goods that were priced by hand before this rule existed."""
        changed = 0
        for product in queryset.filter(cost_price__gt=0):
            product.price = selling_price(product.cost_price)
            product.save(update_fields=['price'])
            changed += 1
        self.message_user(request, f"{changed} {lazy_t('admin_msg_repriced')}")

    @admin.display(description=lazy_t('admin_margin'), ordering='margin_sort')
    def margin(self, obj):
        pct = margin_percent(obj.price, obj.cost_price)
        return '-' if pct is None else f'{pct:.1f}%'

    def get_urls(self):
        # Listed first so it wins over Django's catch-all "<id>/" route.
        return [
            path('<int:pk>/detail/', self.admin_site.admin_view(self.detail_view),
                 name='store_product_detail'),
        ] + super().get_urls()

    def detail_view(self, request, pk):
        """HTML fragment for the picture-click popup on the product list."""
        if not self.has_view_permission(request):
            raise PermissionDenied
        from .reports import product_detail_response
        from .translations import get_translations
        product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
        return product_detail_response(request, product, period_label=get_translations(request)['period_all'])

    @admin.display(description=lazy_t('form_image_label'), ordering='image')
    def image_thumbnail(self, obj):
        """Small square picture for the product list page. Click = detail popup."""
        url = reverse('admin:store_product_detail', args=[obj.pk])
        if not obj.image:
            return format_html('<a href="{}" class="rd-link">-</a>', url)
        return format_html(
            '<a href="{}" class="rd-link rd-thumb-link"><img src="{}" alt="{}" style="width:60px;height:60px;'
            'object-fit:cover;border-radius:6px;" /></a>',
            url,
            obj.image.url,
            obj.name,
        )

    @admin.display(description=lazy_t('form_image_label'))
    def image_preview(self, obj):
        """Larger picture on the product edit page (the upload box itself
        doesn't show the current image)."""
        if not obj or not obj.image:
            return '-'
        return format_html(
            '<img src="{}" alt="{}" style="max-width:250px;max-height:250px;'
            'border-radius:8px;" />',
            obj.image.url,
            obj.name,
        )

    @admin.display(description=lazy_t('admin_stock_status'), ordering='sort_state')
    def stock_status(self, obj):
        state = obj.stock_state      # price-aware, see store/stock_rules.py
        if state == 'out':
            return format_html(
                '<span style="color:#c0392b;font-weight:bold;">{}</span>',
                str(lazy_t('admin_out_of_stock'))
            )

        if state == 'low':
            return format_html(
                '<span style="color:#e67e22;font-weight:bold;">{}</span>',
                str(lazy_t('admin_low_stock_status'))
            )

        return format_html(
            '<span style="color:#27ae60;">{}</span>',
            str(lazy_t('admin_in_stock'))
        )


class HeroSlideForm(forms.ModelForm):
    """Checks the uploaded slide picture: right shape (8:3), big enough, not huge."""

    class Meta:
        model = HeroSlide
        fields = '__all__'

    def clean_image(self):
        from django.core.files.images import get_image_dimensions
        from django.db.models.fields.files import FieldFile

        img = self.cleaned_data.get('image')
        # Only a freshly uploaded file needs checking. An unchanged picture comes
        # back as the stored FieldFile (already 1600x600).
        if not img or isinstance(img, FieldFile):
            return img
        if img.size > HERO_MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(str(lazy_t('hero_err_filesize')).format(mb=HERO_MAX_UPLOAD_MB))
        w, h = get_image_dimensions(img)
        img.seek(0)
        if not w or not h:
            return img
        if abs(w / h - 8 / 3) > 8 / 3 * 0.05:          # within 5 % of 8:3
            raise forms.ValidationError(str(lazy_t('hero_err_ratio')).format(w=w, h=h))
        if w < HERO_MIN_SIZE[0] or h < HERO_MIN_SIZE[1]:
            raise forms.ValidationError(str(lazy_t('hero_err_small')).format(w=w, h=h))
        return img


@admin.register(HeroSlide)
class HeroSlideAdmin(PopupFriendlyAdmin, admin.ModelAdmin):
    """The home page slider (Customize -> Home page slider).

    At most HERO_MAX_SLIDES slides. For each one: search a product by name,
    upload the slide picture, choose the button text / place, set the order.
    The home page shows only the slides made here. To change a slide, open
    it and pick another product or upload another picture.
    """

    form = HeroSlideForm
    list_display = ('slide_image', 'product_name', 'button_position', 'sort_order', 'is_active')
    list_display_links = ('product_name',)
    list_editable = ('sort_order', 'is_active')
    list_per_page = DEFAULT_PAGE_SIZE
    ordering = ('sort_order', 'id')
    fields = ('product', 'image', 'image_preview', 'button_text', 'button_position', 'sort_order', 'is_active')
    readonly_fields = ('image_preview',)
    autocomplete_fields = ('product',)       # searchable by product name
    column_filters = {}

    def get_changelist(self, request, **kwargs):
        return BshopChangeList

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')

    def has_add_permission(self, request):
        if HeroSlide.objects.count() >= HERO_MAX_SLIDES:
            return False
        return super().has_add_permission(request)

    def changelist_view(self, request, extra_context=None):
        if request.method == 'GET' and HeroSlide.objects.count() >= HERO_MAX_SLIDES:
            self.message_user(request, str(lazy_t('hero_full_note')).format(max=HERO_MAX_SLIDES), level='info')
        return super().changelist_view(request, extra_context)

    @admin.display(description=lazy_t('hero_f_image'))
    def slide_image(self, obj):
        if not obj.image:
            return '-'
        return format_html(
            '<img src="{}" alt="{}" style="width:160px;height:60px;object-fit:cover;border-radius:6px;" />',
            obj.image.url, obj.product.name,
        )

    @admin.display(description=lazy_t('hero_f_image'))
    def image_preview(self, obj):
        if not obj or not obj.image:
            return '-'
        return format_html(
            '<img src="{}" alt="{}" style="width:100%;max-width:480px;aspect-ratio:8/3;'
            'object-fit:cover;border-radius:8px;" />',
            obj.image.url, obj.product.name,
        )

    @admin.display(description=lazy_t('hero_f_product'), ordering='product__name')
    def product_name(self, obj):
        return obj.product.name