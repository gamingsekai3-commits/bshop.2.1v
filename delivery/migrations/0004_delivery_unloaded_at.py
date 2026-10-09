from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0003_drivers_as_employees'),
    ]

    operations = [
        migrations.AddField(
            model_name='delivery',
            name='unloaded_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Буулгасан'),
        ),
    ]
