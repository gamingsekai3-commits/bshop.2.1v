from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_profiles(apps, schema_editor):
    """For every auth_user that already exists, create the matching
    Employee row (if is_staff) or Customer row (otherwise). This is what
    migrates your existing accounts into the new tables."""
    User = apps.get_model(settings.AUTH_USER_MODEL.split('.')[0], settings.AUTH_USER_MODEL.split('.')[1])
    Employee = apps.get_model('store', 'Employee')
    Customer = apps.get_model('store', 'Customer')

    for user in User.objects.all():
        if user.is_staff:
            Employee.objects.get_or_create(user=user)
        else:
            Customer.objects.get_or_create(user=user)


def noop_reverse(apps, schema_editor):
    # Nothing to undo on the User table itself; dropping the Employee/
    # Customer tables (handled by the schema reversal) is enough.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0004_product_stock'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # The old store.Order (FK -> old store.Customer) and old
        # store.Customer (a standalone email/password table, unrelated to
        # auth_user) were dead code: never used by any view, only ever
        # registered in the admin. Safe to drop.
        #
        # These are wrapped in SeparateDatabaseAndState with raw "DROP
        # TABLE IF EXISTS" instead of RemoveField/DeleteModel, because on
        # some databases the physical store_order/store_customer tables
        # don't actually exist even though Django's migration history says
        # they should (e.g. if they were dropped manually, or the DB was
        # provisioned separately from the migration history). Using plain
        # DeleteModel would fail with "relation does not exist" in that
        # case; IF EXISTS makes this migration safe to run either way,
        # while still updating Django's internal model state correctly.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # NOTE: the old store.Order is NOT removed here any more.
                # 0004_delete_order already deletes it, and since these two
                # migrations sit on branches that were later merged, Django
                # could end up replaying both deletions and crashing with
                # KeyError: ('store', 'order'). Deleting it once, in
                # 0004_delete_order, is enough. The DROP TABLE below is kept
                # because it is guarded with IF EXISTS and is harmless.
                migrations.DeleteModel(
                    name='Customer',
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql='DROP TABLE IF EXISTS store_order;',
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql='DROP TABLE IF EXISTS store_customer;',
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),

        migrations.CreateModel(
            name='Employee',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(blank=True, default='', max_length=20)),
                ('position', models.CharField(blank=True, default='Ажилтан', max_length=100)),
                ('hired_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='employee_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Employee',
                'verbose_name_plural': 'Employees',
            },
        ),
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(blank=True, default='', max_length=20)),
                ('address', models.CharField(blank=True, default='', max_length=255)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='customer_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Customer',
                'verbose_name_plural': 'Customers',
            },
        ),

        migrations.RunPython(backfill_profiles, noop_reverse),
    ]