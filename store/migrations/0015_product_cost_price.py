from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0014_product_rating_product_created_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='cost_price',
            field=models.DecimalField(
                decimal_places=2, default=0.0, max_digits=10,
                help_text='What one unit costs the shop to buy/make. Used for the Expense and Profit figures in Reports > Overview.',
            ),
        ),
    ]
