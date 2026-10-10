from django.db import migrations


def add_driver_positions(apps, schema_editor):
    """Every active driver gets the "Хүргэгч" position row, so the employee
    form shows the box ticked. Without this, an existing Admin who is also a
    driver would lose the driver site the first time their form is saved."""
    Driver = apps.get_model('delivery', 'Driver')
    Employee = apps.get_model('store', 'Employee')
    EmployeePosition = apps.get_model('store', 'EmployeePosition')
    for driver in Driver.objects.filter(is_active=True):
        employee, _ = Employee.objects.get_or_create(
            user_id=driver.user_id,
            defaults={'position': 'Хүргэгч', 'phone': driver.phone, 'is_active': driver.is_active},
        )
        EmployeePosition.objects.get_or_create(employee=employee, position='Хүргэгч')


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0004_delivery_unloaded_at'),
        ('store', '0022_employee_positions'),
    ]

    operations = [
        migrations.RunPython(add_driver_positions, migrations.RunPython.noop),
    ]
