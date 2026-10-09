from django.db import migrations
from django.utils import timezone


def add_existing_stock(apps, schema_editor):
    """Stock already in the warehouse counts as an expense too: one 'opening'
    entry per product, for its current stock, at its current cost price."""
    Product = apps.get_model('store', 'Product')
    StockEntry = apps.get_model('store', 'StockEntry')
    now = timezone.now()
    StockEntry.objects.bulk_create([
        StockEntry(product=p, name=p.name, quantity=p.stock, unit_cost=p.cost_price,
                   is_opening=True, created_at=now)
        for p in Product.objects.filter(stock__gt=0)
    ])


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0016_stockentry'),
    ]

    operations = [
        migrations.RunPython(add_existing_stock, migrations.RunPython.noop),
    ]
