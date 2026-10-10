"""One-off: give goods that were priced by hand before the mark-up rule existed
a cost price and a selling price.

    python manage.py reprice_products            # preview only, changes nothing
    python manage.py reprice_products --apply    # do it

For every product that has a price but no cost price yet, the current price is
taken as what the goods cost (cost_price), the selling price becomes
cost + mark-up (store/pricing.py), and its opening-stock entry is given that
unit cost so the stock shows up as an expense. Products that already have a
cost price are skipped, so running it twice never stacks a second mark-up.
Past orders keep the price they were sold at (OrderItem.price is untouched).
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from store.models import Product, StockEntry
from store.pricing import selling_price


class Command(BaseCommand):
    help = 'Set cost price and mark-up selling price on products that have no cost price yet.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Save the changes (without it this is only a preview).')

    def handle(self, *args, **options):
        apply = options['apply']
        todo = Product.objects.filter(cost_price=0, price__gt=0).order_by('name')
        count = 0
        with transaction.atomic():
            for product in todo:
                cost = product.price
                new_price = selling_price(cost)
                self.stdout.write(f'{product.name}: cost {cost:,.0f} -> price {new_price:,.0f}')
                count += 1
                if not apply:
                    continue
                product.cost_price = cost
                product.price = new_price
                product.save(update_fields=['cost_price', 'price'])
                StockEntry.objects.filter(product=product, is_opening=True).update(unit_cost=cost)
        if apply:
            self.stdout.write(self.style.SUCCESS(f'Re-priced {count} product(s).'))
        else:
            self.stdout.write(f'{count} product(s) would change. Run again with --apply to save.')
