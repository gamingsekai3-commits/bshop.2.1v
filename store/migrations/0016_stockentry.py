import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0015_product_cost_price'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='cost_price',
            field=models.DecimalField(
                decimal_places=2, default=0.0, max_digits=10,
                help_text='Default purchase price of one unit. Pre-fills the price when you add stock; each stock addition is recorded as an expense.',
            ),
        ),
        migrations.CreateModel(
            name='StockEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, default='', max_length=100)),
                ('quantity', models.PositiveIntegerField()),
                ('unit_cost', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('is_opening', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                              related_name='stock_entries', to='store.product')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
