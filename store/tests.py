from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from cart.models import Order, OrderItem
from .models import Category, Customer, Employee, Product, StockEntry
from .pricing import margin_percent, markup_percent, selling_price


class PricingRuleTests(TestCase):
    def test_cheap_goods_get_30_and_dear_goods_get_20(self):
        self.assertEqual(markup_percent(3000), Decimal('30'))
        self.assertEqual(markup_percent(10000), Decimal('30'))
        self.assertEqual(markup_percent(10_000_000), Decimal('20'))
        self.assertEqual(markup_percent(67_000_000), Decimal('20'))

    def test_markup_only_ever_goes_down_as_cost_goes_up(self):
        costs = [5_000, 20_000, 100_000, 500_000, 2_000_000, 8_000_000, 50_000_000]
        marks = [markup_percent(c) for c in costs]
        self.assertEqual(marks, sorted(marks, reverse=True))
        for m in marks:
            self.assertTrue(Decimal('20') <= m <= Decimal('30'))

    def test_selling_price_is_within_20_to_30_percent_of_cost(self):
        for cost in (1_500, 3_000, 45_000, 100_000, 1_200_000, 25_000_000):
            price = selling_price(cost)
            self.assertGreaterEqual(price, Decimal(cost) * Decimal('1.20'))
            # rounding up to 10 can add at most 10 on top of the 30 % ceiling
            self.assertLessEqual(price, Decimal(cost) * Decimal('1.30') + 10)

    def test_no_cost_means_no_automatic_price(self):
        self.assertIsNone(selling_price(0))
        self.assertIsNone(margin_percent(1000, 0))


# The real settings use a hashed-static manifest that only exists after
# collectstatic; plain storage keeps page rendering working inside tests.
@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class StockToProfitFlowTests(TestCase):
    """Buy stock (expense) -> price set automatically -> customer buys (income) -> profit."""

    def setUp(self):
        self.staff = User.objects.create_superuser('boss', 'b@x.mn', 'pw')
        self.cat = Category.objects.create(name='Phones')
        self.product = Product.objects.create(name='Phone', category=self.cat, price=0, stock=0)
        self.client.force_login(self.staff)

    def restock(self, qty, cost):
        return self.client.post(reverse('stock'), {
            'product_id': self.product.id, 'quantity': qty, 'unit_cost': cost})

    def test_admin_product_list_renders_in_both_languages(self):
        # Regression: a '%' in an action's description crashed this page.
        for lang in ('mn', 'en'):
            self.client.cookies['site_lang'] = lang
            resp = self.client.get(reverse('admin:store_product_changelist'))
            self.assertEqual(resp.status_code, 200, lang)
            self.assertContains(resp, 'reprice_from_cost')

    def test_reprice_action_runs(self):
        self.product.cost_price = Decimal('100000')
        self.product.save()
        resp = self.client.post(reverse('admin:store_product_changelist'), {
            'action': 'reprice_from_cost', '_selected_action': [self.product.id]}, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, selling_price(100000))

    def test_stock_page_shows_cost_field_and_price_preview(self):
        resp = self.client.get(reverse('stock'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="unit_cost"')
        self.assertContains(resp, 'id="se-stock-price"')

    def test_restock_records_expense_and_sets_price(self):
        self.restock(10, 100000)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.product.cost_price, Decimal('100000'))
        self.assertEqual(self.product.price, selling_price(100000))
        entry = StockEntry.objects.get()
        self.assertEqual(entry.total_cost, Decimal('1000000'))   # 10 x 100,000 = expense

    def test_second_delivery_at_new_cost_reprices(self):
        self.restock(5, 100000)
        self.restock(5, 120000)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, selling_price(120000))
        self.assertEqual(sum(e.total_cost for e in StockEntry.objects.all()), Decimal('1100000'))

    def test_restock_without_cost_keeps_price(self):
        self.product.price = Decimal('5000')
        self.product.save()
        self.restock(3, 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal('5000'))

    def test_admin_edit_reprices_on_stock_increase_but_not_over_manual_price(self):
        url = reverse('admin:store_product_change', args=[self.product.id])
        # not exercised through the form (image is required there); use the admin method directly
        from django.contrib import admin
        from django.test import RequestFactory
        ma = admin.site._registry[Product]

        class FakeForm:
            def __init__(self, changed): self.changed_data = changed

        p = Product.objects.get(pk=self.product.pk)
        p.cost_price, p.stock = Decimal('100000'), 4
        ma.save_model(RequestFactory().post('/'), p, FakeForm(['stock', 'cost_price']), change=True)
        p.refresh_from_db()
        self.assertEqual(p.price, selling_price(100000))

        p.stock, p.price = 9, Decimal('777777')            # admin typed their own price
        ma.save_model(RequestFactory().post('/'), p, FakeForm(['stock', 'price']), change=True)
        p.refresh_from_db()
        self.assertEqual(p.price, Decimal('777777'))

    def test_customer_order_is_income_and_profit_is_income_minus_expense(self):
        self.restock(10, 100000)                      # expense 1,000,000
        self.product.refresh_from_db()
        price = self.product.price
        self.client.logout()

        self.client.post(reverse('cart_add'), {
            'action': 'post', 'product_id': self.product.id, 'product_qty': 3})
        self.client.post(reverse('order_create'), {'name': 'A', 'phone': '1', 'address': 'UB'})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)       # sold straight from stock
        self.assertEqual(Order.objects.count(), 1)

        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin:report_overview'))
        self.assertEqual(resp.context['income'], int(price * 3))
        self.assertEqual(resp.context['expense'], 1_000_000)
        self.assertEqual(resp.context['profit'], int(price * 3) - 1_000_000)


class RepriceExistingProductsTests(TestCase):
    def setUp(self):
        cat = Category.objects.create(name='Food')
        self.old = Product.objects.create(name='Bread', category=cat, price=3000, stock=10)
        StockEntry.objects.create(product=self.old, name='Bread', quantity=10, unit_cost=0, is_opening=True)

    def run_cmd(self, *args):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('reprice_products', *args, stdout=out)
        return out.getvalue()

    def test_preview_changes_nothing(self):
        self.run_cmd()
        self.old.refresh_from_db()
        self.assertEqual((self.old.price, self.old.cost_price), (3000, 0))

    def test_apply_adds_markup_sets_cost_and_expense_and_is_idempotent(self):
        self.run_cmd('--apply')
        self.old.refresh_from_db()
        self.assertEqual(self.old.cost_price, Decimal('3000'))
        self.assertEqual(self.old.price, Decimal('3900'))
        self.assertEqual(StockEntry.objects.get().total_cost, Decimal('30000'))
        self.run_cmd('--apply')                      # second run must not stack another mark-up
        self.old.refresh_from_db()
        self.assertEqual(self.old.price, Decimal('3900'))

    def test_past_orders_keep_their_price(self):
        order = Order.objects.create(name='A', phone='1', address='x')
        OrderItem.objects.create(order=order, product=self.old, price=3000, quantity=2)
        self.run_cmd('--apply')
        self.assertEqual(OrderItem.objects.get().price, Decimal('3000'))


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class StockPageSortingTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser('boss', 'b@x.mn', 'pw'))
        a, b = Category.objects.create(name='Aaa'), Category.objects.create(name='Zzz')
        # 12 products -> 2 pages at the default 10 rows, to prove sorting spans pages
        for i in range(12):
            Product.objects.create(name=f'P{i:02d}', category=a if i % 2 else b,
                                   price=1000 * (i + 1), stock=0 if i == 3 else 50 - i)

    def names(self, qs=''):
        resp = self.client.get(reverse('stock') + qs)
        self.assertEqual(resp.status_code, 200)
        return [p.name for p in resp.context['products']], resp

    def test_every_column_header_shows_an_indicator(self):
        _n, resp = self.names()
        self.assertEqual(resp.content.decode().count('stock-sort-mark">⇅'), 6)

    def test_price_sort_covers_all_pages_and_flips(self):
        asc, _ = self.names('?sort=price&dir=asc')
        desc, _ = self.names('?sort=price&dir=desc')
        self.assertEqual(asc[0], 'P00')
        self.assertEqual(desc[0], 'P11')                  # most expensive is on page 1, not page 2
        page2, _ = self.names('?sort=price&dir=desc&p=2')
        self.assertEqual(page2, ['P01', 'P00'])

    def test_stock_and_status_sort(self):
        by_stock, _ = self.names('?sort=stock&dir=asc')
        self.assertEqual(by_stock[0], 'P03')              # the sold-out one
        by_status, _ = self.names('?sort=status&dir=asc')
        self.assertEqual(by_status[0], 'P03')             # out -> low -> ok

    def test_click_cycle_asc_desc_off(self):
        _n, resp = self.names('?sort=name&dir=asc')
        self.assertEqual(resp.context['sort_columns']['name']['mark'], '▲')
        self.assertIn('dir=desc', resp.context['sort_columns']['name']['url'])
        _n, resp = self.names('?sort=name&dir=desc')
        self.assertEqual(resp.context['sort_columns']['name']['mark'], '▼')
        self.assertNotIn('sort=', resp.context['sort_columns']['name']['url'])   # third click clears

    def test_bad_sort_value_is_ignored(self):
        names, _ = self.names('?sort=password&dir=desc')
        self.assertEqual(names[0], 'P00')


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class SortAcrossAllPagesTests(TestCase):
    """The order must cover every row, not just the 10 on screen."""

    def setUp(self):
        self.client.force_login(User.objects.create_superuser('boss', 'b@x.mn', 'pw'))
        a, b = Category.objects.create(name='Aaa'), Category.objects.create(name='Zzz')
        self.products = []
        for i in range(25):       # 25 rows -> 3 pages at 10 per page
            self.products.append(Product.objects.create(
                name=f'P{i:02d}', category=a if i % 2 else b, price=1000 * (i + 1),
                cost_price=500 * (i + 1) if i % 5 else 0, stock=0 if i == 7 else i + 1))

    def first_ids(self, url):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, url)
        return [o.pk for o in resp.context['cl'].result_list], resp

    # ---- admin lists (Django ?o=) -----------------------------------------
    def test_every_product_column_can_be_sorted_by_the_server(self):
        resp = self.client.get(reverse('admin:store_product_changelist'))
        html = resp.content.decode()
        sortable = html.count('sortable column-')
        # image, name, category, price, margin, stock, stock_status, is_sale, rating, status, is_active
        self.assertGreaterEqual(sortable, 11)

    def test_product_price_sort_spans_pages(self):
        url = reverse('admin:store_product_changelist')
        col = [i for i, f in enumerate(self._list_display()) if f == 'price'][0] + 1   # +1: checkbox column
        top, _ = self.first_ids(f'{url}?o=-{col}')
        self.assertEqual(top[0], self.products[-1].pk)          # dearest on page 1
        last, _ = self.first_ids(f'{url}?o={col}&p=3')
        self.assertEqual(last[-1], self.products[-1].pk)

    def _list_display(self):
        from django.contrib import admin
        return list(admin.site._registry[Product].list_display)

    def test_computed_columns_sort(self):
        url = reverse('admin:store_product_changelist')
        cols = self._list_display()
        status = cols.index('stock_status') + 1
        ids, _ = self.first_ids(f'{url}?o={status}')
        self.assertEqual(ids[0], self.products[7].pk)            # sold out first
        margin = cols.index('margin') + 1
        ids, _ = self.first_ids(f'{url}?o=-{margin}')            # highest mark-up first, no crash
        self.assertEqual(len(ids), 10)

    def test_order_total_sorts(self):
        for i, qty in enumerate((1, 5, 3)):
            o = Order.objects.create(name=f'C{i}', phone='1', address='x')
            OrderItem.objects.create(order=o, product=self.products[0], price=1000, quantity=qty)
        from django.contrib import admin
        col = list(admin.site._registry[Order].list_display).index('get_total_price') + 1
        resp = self.client.get(reverse('admin:cart_order_changelist') + f'?o=-{col}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([o.name for o in resp.context['cl'].result_list], ['C1', 'C2', 'C0'])

    # ---- reports (?sort=) --------------------------------------------------
    def make_sales(self):
        for i, p in enumerate(self.products):
            if p.stock:
                o = Order.objects.create(name='c', phone='1', address='x')
                OrderItem.objects.create(order=o, product=p, price=p.price, quantity=1)

    def test_report_headers_show_both_arrows_and_light_the_active_one(self):
        """Every report header has a \u25B2 and a \u25BC link; th[data-dir] says which one is lit."""
        self.make_sales()
        base = reverse('admin:report_inventory') + '?date_from=2000-01-01&date_to=2999-12-31'
        resp = self.client.get(base)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-server-sort')                # sorted on the server, swapped in place by JS
        self.assertContains(resp, 'class="rs-dir rs-up"')
        self.assertContains(resp, 'class="rs-dir rs-down"')
        self.assertNotContains(resp, 'rs-mark')                      # the old single \u21C5 mark is gone
        self.assertContains(resp, 'data-dir=""')                     # nothing lit yet
        cols = resp.context['columns']
        self.assertEqual({c[5] for c in cols}, {''})
        # Ascending: the \u25B2 link of that column turns the sort off, its \u25BC link switches to descending.
        asc = self.client.get(f'{base}&sort=2&dir=asc').context['columns'][2]
        self.assertEqual(asc[5], 'asc')
        self.assertNotIn('sort=', asc[9])                            # up_url: click the lit \u25B2 again = off
        self.assertIn('dir=desc', asc[10])                           # down_url
        desc = self.client.get(f'{base}&sort=2&dir=desc').context['columns'][2]
        self.assertEqual(desc[5], 'desc')
        self.assertIn('dir=asc', desc[9])
        self.assertNotIn('sort=', desc[10])
        # the header text still cycles asc -> desc -> off
        self.assertIn('dir=desc', asc[4])
        self.assertNotIn('sort=', desc[4])

    def test_report_rows_carry_what_the_browser_needs_to_sort_in_place(self):
        """data-sv / data-n / data-ord let JS re-order a one-page report exactly like the server."""
        self.make_sales()
        base = reverse('admin:report_inventory') + '?date_from=2000-01-01&date_to=2999-12-31'
        multi = self.client.get(base)                                # 10 per page, more rows than that
        self.assertNotContains(multi, 'data-all-rows')
        one = self.client.get(f'{base}&per_page=100&sort=2&dir=desc')
        self.assertContains(one, 'data-all-rows')                    # every row is on this page
        self.assertContains(one, 'data-ord="0"')
        self.assertContains(one, ' data-n>')                         # numeric cells are flagged
        rows = one.context['rows']
        ords = [r[0][5] for r in rows]
        self.assertNotEqual(ords, sorted(ords))                      # sorted by price desc, so no longer in the original order
        prices = [float(r[2][3]) for r in rows]                      # data-sv of the price column
        self.assertEqual(prices, sorted(prices, reverse=True))

    # ---- smoke: no column of any list or report may crash when sorted -------
    def test_every_column_of_every_list_and_report_sorts_without_error(self):
        from django.contrib import admin
        self.make_sales()
        Customer.objects.get_or_create(user=User.objects.create_user('cust', 'c@x.mn', 'pw'))
        for model in (Category, Employee, Customer, Product, Order):
            ma = admin.site._registry[model]
            url = reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist')
            for i in range(1, len(ma.list_display) + 1):
                for sign in ('', '-'):
                    resp = self.client.get(f'{url}?o={sign}{i}')
                    self.assertEqual(resp.status_code, 200, (model.__name__, i, sign))
        for name in ('report_inventory', 'report_orders', 'report_customers'):
            base = reverse(f'admin:{name}') + '?date_from=2000-01-01&date_to=2999-12-31'
            ncols = len(self.client.get(base).context['columns'])
            for i in range(ncols):
                for d in ('asc', 'desc'):
                    resp = self.client.get(f'{base}&sort={i}&dir={d}')
                    self.assertEqual(resp.status_code, 200, (name, i, d))