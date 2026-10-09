from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0020_heroslide'),
    ]

    operations = [
        migrations.RemoveField(model_name='heroslide', name='badge'),
        migrations.RemoveField(model_name='heroslide', name='headline'),
        migrations.RemoveField(model_name='heroslide', name='tagline'),
        migrations.RemoveField(model_name='heroslide', name='theme'),
        migrations.AddField(
            model_name='heroslide',
            name='image',
            field=models.ImageField(default='', help_text='Заавал 1600x600 px (8:3 харьцаатай) зураг оруулна. Автоматаар 1600x600 болгож, чанарыг тохируулна.', upload_to='uploads/hero/', verbose_name='Слайдын зураг'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='heroslide',
            name='button_position',
            field=models.CharField(choices=[('left', 'Зүүн доор'), ('center', 'Дунд доор'), ('right', 'Баруун доор')], default='left', max_length=10, verbose_name='Товчны байрлал'),
        ),
        migrations.AlterField(
            model_name='heroslide',
            name='product',
            field=models.ForeignKey(help_text='Нэрээр нь хайж сонгоно. Слайдны товч энэ барааны дэлгэрэнгүй хуудас руу очно.', on_delete=models.deletion.CASCADE, related_name='hero_slides', to='store.product', verbose_name='Бүтээгдэхүүн'),
        ),
        migrations.AlterModelOptions(
            name='heroslide',
            options={'ordering': ['sort_order', 'id'], 'verbose_name': 'Нүүр слайд', 'verbose_name_plural': 'Нүүр хуудасны слайдер'},
        ),
    ]
