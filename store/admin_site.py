"""A thin wrapper around Django's admin site so the app and model names in
the sidebar follow the language button too.

Django builds those names from each model's Meta.verbose_name. Changing them
there would mean writing migrations just to rename labels, so instead we let
Django build its normal list and swap the display names on the way out, using
the same `T` dict the rest of the site uses.

Everything else (permissions, registration, URLs) is stock Django - existing
`admin.site.register(...)` calls keep working untouched.
"""

from urllib.parse import urlencode

from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.urls import path, reverse, reverse_lazy

from .translations import lazy_t

# app label -> key in translations.py
APP_LABELS = {
    'store': 'admin_app_store',
    'customize': 'admin_app_customize',
    'cart': 'admin_app_cart',
    'reports': 'admin_app_reports',
    'delivery': 'dl_app',
}

# Fixed sidebar order, independent of language.
#
# Django's default get_app_list() sorts apps alphabetically by their
# (already-translated) name. That looked fine in English, but
# SiteLanguageMiddleware also switches Django's own translations on, so
# 'auth's built-in name translates to "Нэвтрэлт ба зөвшөөрөл" while our own
# 'store'/'cart' names are still plain "Store"/"Cart" at that point (we
# rename them further down, after the sort already happened). Cyrillic
# letters sort after Latin ones, so the same three groups landed in a
# different order in each language: Auth, Cart, Store in English but
# Cart, Store, Auth in Mongolian. Sorting by this fixed list instead keeps
# the sidebar in the same order no matter which language is active.
APP_ORDER = ['store', 'cart', 'delivery', 'customize', 'reports', 'auth']


# "app_label.modelname" -> (singular key, plural key)
MODEL_LABELS = {
    'store.category': ('admin_model_category', 'admin_categories'),
    'store.product': ('admin_model_product', 'admin_products'),
    'store.heroslide': ('hero_model', 'hero_models'),
    'store.employee': ('admin_model_employee', 'admin_employees'),
    'store.customer': ('admin_model_customer', 'admin_model_customers'),
    'cart.order': ('admin_model_order', 'admin_orders'),
    'cart.orderitem': ('admin_model_orderitem', 'admin_order_items'),
    'delivery.driver': ('dl_model_driver', 'dl_drivers'),
    'delivery.delivery': ('dl_model_delivery', 'dl_deliveries'),
    'delivery.deliveryhistory': ('dl_model_history', 'dl_model_history'),
}


class BshopAdminSite(AdminSite):
    # These three show up in the browser tab, the header and above the
    # dashboard. lazy_t means they are looked up per request, not once at
    # startup, so they change as soon as the visitor flips the language.
    site_title = lazy_t('admin_site_title')
    site_header = lazy_t('admin_site_header')
    index_title = lazy_t('admin_index_title')

    @method_decorator(never_cache)
    def login(self, request, extra_context=None):
        """Admins don't have their own login page any more: everyone signs in
        through Work Web (/work/). Anyone who lands here (an expired session on
        an /admin/ page, a typed URL) is sent there, keeping the deep link
        (?next=/admin/some/page/) so they come back to the same place.

        Already signed in as staff -> stock behaviour (straight to ?next= / index).
        """
        user = request.user
        if user.is_authenticated and user.is_active and user.is_staff:
            return super().login(request, extra_context)
        url = reverse('work_login')
        next_url = request.GET.get('next', '')
        if next_url and next_url.startswith('/') and not next_url.startswith('//'):
            url += '?' + urlencode({'next': next_url})
        return redirect(url)

    def get_urls(self):
        # Report pages live under /admin/reports/... and go through
        # admin_view(), so they need a staff login like every other admin
        # page. Imported here (not at the top) because store.reports pulls in
        # models, which aren't ready yet when this module is first loaded.
        from .reports import DETAIL_VIEWS, REPORTS

        report_urls = [
            path(url_path, self.admin_view(lambda request, view=view: view(self, request)), name=name)
            for name, url_path, _key, view in REPORTS
        ]
        report_urls += [
            path(url_path, self.admin_view(lambda request, pk, view=view: view(self, request, pk)), name=name)
            for name, url_path, view in DETAIL_VIEWS
        ]
        first = reverse_lazy(f'admin:{REPORTS[0][0]}')
        index = path(
            'reports/',
            self.admin_view(lambda request: redirect(first)),
            name='reports_index',
        )
        return report_urls + [index] + super().get_urls()

    def _reports_app(self):
        """The "Reports" sidebar group. It isn't a Django app or model, just
        a list of links, so it's added by hand in the same dict shape Django
        uses for real apps - that way admin/app_list.html and
        nav-sidebar-accordion.js treat it like any other group."""
        from .reports import REPORTS

        models = []
        for name, _path, key, _view in REPORTS:
            models.append({
                'name': lazy_t(key),
                'object_name': name,       # -> CSS class "model-report_sales"
                'perms': {},
                'admin_url': reverse(f'admin:{name}'),
                'add_url': None,
            })
        return {
            'name': lazy_t('admin_app_reports'),
            'app_label': 'reports',
            # Must not be empty: app_list.html marks a group "current-app"
            # when app_url is found inside request.path, and '' is found in
            # every path. /admin/reports/ redirects to the first report (see
            # get_urls) so the group title stays a working link too.
            'app_url': models[0]['admin_url'].rsplit('/', 2)[0] + '/',
            'has_module_perms': True,
            'models': models,
        }

    def _move_to_customize(self, app_list):
        """The home page slider is a site setting, not store data, so it gets
        its own "Customize" sidebar group (same dict shape Django uses)."""
        moved = []
        for app in app_list:
            if app.get('app_label') != 'store':
                continue
            keep = []
            for model in app.get('models', []):
                if model.get('object_name', '').lower() == 'heroslide':
                    moved.append(model)
                else:
                    keep.append(model)
            app['models'] = keep
        if moved:
            app_list.append({
                'name': lazy_t('admin_app_customize'),
                'app_label': 'customize',
                'app_url': moved[0].get('admin_url') or '/admin/store/heroslide/',
                'has_module_perms': True,
                'models': moved,
            })

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        if app_label is None:
            self._move_to_customize(app_list)
        if app_label is None and request.user.is_staff:
            app_list.append(self._reports_app())
        for app in app_list:
            key = APP_LABELS.get(app.get('app_label'))
            if key:
                app['name'] = lazy_t(key)
            for model in app.get('models', []):
                object_name = model.get('object_name', '')
                lookup = f"{app.get('app_label')}.{object_name.lower()}"
                labels = MODEL_LABELS.get(lookup)
                if labels:
                    # The sidebar and dashboard show the plural form.
                    model['name'] = lazy_t(labels[1])

        # Re-sort by app_label using our own fixed order instead of the
        # (language-dependent) name Django's super() call already sorted by.
        # Apps not listed in APP_ORDER (there currently are none) keep
        # appearing, just after the ones we did list.
        app_list.sort(key=lambda app: (
            APP_ORDER.index(app.get('app_label'))
            if app.get('app_label') in APP_ORDER
            else len(APP_ORDER)
        ))
        return app_list


class BshopAdminConfig(AdminConfig):
    """Points django.contrib.admin at BshopAdminSite. Wired up by swapping
    'django.contrib.admin' for this class in INSTALLED_APPS."""

    default_site = 'store.admin_site.BshopAdminSite'