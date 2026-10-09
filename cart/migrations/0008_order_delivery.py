import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import F


def backfill_delivered_at(apps, schema_editor):
    """Orders delivered before this feature have no delivery time; use the
    order date so they keep counting in the income charts."""
    Order = apps.get_model('cart', 'Order')
    Order.objects.filter(status='delivered', delivered_at__isnull=True).update(delivered_at=F('created_at'))


class Migration(migrations.Migration):

    dependencies = [
        ('cart', '0007_alter_orderitem_options_alter_order_address_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='courier',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deliveries', to=settings.AUTH_USER_MODEL, verbose_name='Хүргэгч'),
        ),
        migrations.AddField(
            model_name='order',
            name='picked_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Хүргэлтэд авсан огноо'),
        ),
        migrations.AddField(
            model_name='order',
            name='delivered_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Хүргэсэн огноо'),
        ),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('pending', 'Хүлээгдэж буй'), ('confirmed', 'Хүргэлтэд авсан'), ('delivered', 'Хүргэлт дууссан'), ('cancelled', 'Цуцлагдсан')], default='pending', max_length=20, verbose_name='Төлөв'),
        ),
        migrations.RunPython(backfill_delivered_at, migrations.RunPython.noop),
    ]
