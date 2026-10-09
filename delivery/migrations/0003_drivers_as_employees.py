from django.db import migrations


def add_existing_drivers(apps, schema_editor):
    Driver = apps.get_model('delivery', 'Driver')
    Employee = apps.get_model('store', 'Employee')
    for driver in Driver.objects.all():
        Employee.objects.get_or_create(
            user_id=driver.user_id,
            defaults={'position': 'Хүргэгч', 'phone': driver.phone, 'is_active': driver.is_active},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0002_initial'),
        ('store', '0019_is_sale_label'),
    ]

    operations = [
        migrations.RunPython(add_existing_drivers, migrations.RunPython.noop),
    ]