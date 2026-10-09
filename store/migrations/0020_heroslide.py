from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0019_is_sale_label'),
    ]

    operations = [
        migrations.CreateModel(
            name='HeroSlide',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('badge', models.CharField(blank=True, default='', help_text='Жишээ: Хамгийн эрэлттэй, Шинэ, -20%. Хоосон бол харагдахгүй.', max_length=40, verbose_name='Шошго')),
                ('headline', models.CharField(blank=True, default='', help_text='Хоосон бол барааны нэр харагдана.', max_length=100, verbose_name='Гарчиг')),
                ('tagline', models.CharField(blank=True, default='', help_text='Хоосон бол барааны тайлбар харагдана.', max_length=200, verbose_name='Тайлбар')),
                ('button_text', models.CharField(blank=True, default='', help_text='Хоосон бол "Дэлгэрэнгүй" гэж харагдана.', max_length=30, verbose_name='Товчны бичиг')),
                ('theme', models.CharField(choices=[('purple', 'Ягаан / хөх'), ('gold', 'Алтлаг'), ('light', 'Цайвар'), ('blue', 'Цэнхэр'), ('red', 'Улаан'), ('green', 'Ногоон')], default='purple', max_length=10, verbose_name='Дэвсгэр өнгө')),
                ('sort_order', models.PositiveSmallIntegerField(default=0, help_text='Бага тоо түрүүлж гарна.', verbose_name='Дараалал')),
                ('is_active', models.BooleanField(default=True, help_text='Идэвхгүй слайд нүүр хуудсанд харагдахгүй.', verbose_name='Идэвхтэй эсэх')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hero_slides', to='store.product', verbose_name='Бүтээгдэхүүн')),
            ],
            options={
                'verbose_name': 'Нүүр хуудасны слайд',
                'verbose_name_plural': 'Нүүр хуудасны слайд',
                'ordering': ['sort_order', 'id'],
            },
        ),
    ]
