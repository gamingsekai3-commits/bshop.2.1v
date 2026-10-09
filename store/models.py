from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

from .translations import active_language, lazy_t, translate_category_name

class ActiveManager(models.Manager):
    """Shortcut for "only the rows that are switched on".

    Every table below keeps an `is_active` flag instead of being deleted, so
    `Product.objects.all()` still returns everything (that is what the admin
    needs to see) while `Product.active.all()` returns only what the public
    storefront should show.
    """

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=50, verbose_name=lazy_t('admin_col_name'))
    # Soft delete: switch this off instead of deleting the row. Inactive
    # categories disappear from the storefront but keep their products and
    # their order history intact, and can be switched back on any time.
    is_active = models.BooleanField(
        default=True,
        verbose_name=lazy_t('admin_col_is_active'),
        help_text=lazy_t('help_category_active'),
    )

    objects = models.Manager()
    active = ActiveManager()

    def __str__(self):
        # Dropdowns / filters / admin show the name in the current site language.
        return translate_category_name(self.name, active_language())
    class Meta:
        verbose_name = lazy_t('admin_model_category')
        verbose_name_plural = lazy_t('admin_categories')


class Employee(models.Model):
    """A real, separate table for staff accounts. Linked 1-to-1 to Django's
    built-in auth User (which still handles login/passwords/permissions) so
    that authentication keeps working, but staff-only details live here
    instead of being bolted onto the User model."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='employee_profile',
    )
    phone = models.CharField(max_length=20, blank=True, default="", verbose_name=lazy_t('f_phone'))
    position = models.CharField(max_length=100, blank=True, default="Employee", verbose_name=lazy_t('f_position'))
    hired_at = models.DateTimeField(auto_now_add=True, verbose_name=lazy_t('f_hired_at'))
    # Soft delete. Switching an employee off also switches off their login
    # (see save() below), which is the point: a person who has left should
    # not be able to sign in, but their name must stay on the orders and
    # admin log entries they created.
    is_active = models.BooleanField(
        default=True,
        verbose_name=lazy_t('admin_col_is_active'),
        help_text=lazy_t('help_employee_active'),
    )

    objects = models.Manager()
    active = ActiveManager()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Keep the auth User in step so login is actually blocked/allowed.
        if self.user_id and self.user.is_active != self.is_active:
            self.user.is_active = self.is_active
            self.user.save(update_fields=['is_active'])

    def __str__(self):
        return self.user.username

    class Meta:
        verbose_name = lazy_t('admin_model_employee')
        verbose_name_plural = lazy_t('admin_employees')


class Customer(models.Model):
    """A real, separate table for customer accounts. Linked 1-to-1 to the
    built-in auth User the same way Employee is."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customer_profile',
    )
    phone = models.CharField(max_length=20, blank=True, default="", verbose_name=lazy_t('f_phone'))
    address = models.CharField(max_length=255, blank=True, default="", verbose_name=lazy_t('f_address'))
    # Soft delete, same idea as Employee: blocks login, keeps past orders.
    is_active = models.BooleanField(
        default=True,
        verbose_name=lazy_t('admin_col_is_active'),
        help_text=lazy_t('help_customer_active'),
    )

    objects = models.Manager()
    active = ActiveManager()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.user_id and self.user.is_active != self.is_active:
            self.user.is_active = self.is_active
            self.user.save(update_fields=['is_active'])

    def __str__(self):
        return self.user.username

    class Meta:
        verbose_name = lazy_t('admin_model_customer')
        verbose_name_plural = lazy_t('admin_model_customers')


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    """Whenever a new auth User is created, drop them into the Employee
    table if they're staff, or the Customer table otherwise. Runs for both
    the public registration form and the "Add employee" admin form, since
    both just create a User (the employee form sets is_staff=True first)."""
    if not created:
        return
    if instance.is_staff:
        Employee.objects.get_or_create(user=instance)
    else:
        Customer.objects.get_or_create(user=instance)


class Product(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name=lazy_t('admin_col_name')
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=lazy_t('f_price'),
    )
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=lazy_t('admin_cost_price'),
        help_text=lazy_t('help_cost_price'),
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        default=1,
        verbose_name=lazy_t('f_category'),
    )
    description = models.TextField(
        blank=True,
        max_length=500,
        default="",
        null=True,
        verbose_name=lazy_t('f_description'),
    )
    image = models.ImageField(
        upload_to='uploads/product/',
        blank=True,
        null=True,
        verbose_name=lazy_t('f_image'),
    )
    is_sale = models.BooleanField(default=False, verbose_name=lazy_t('f_is_sale'))
    sale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name=lazy_t('f_sale_price'),
    )
    stock = models.PositiveIntegerField(
        default=0,
        verbose_name=lazy_t('f_stock'),
        help_text=lazy_t('help_stock'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=lazy_t('admin_col_is_active'),
        help_text=lazy_t('help_product_active'),
    )
    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        default=0,
        verbose_name=lazy_t('f_rating'),
        help_text=lazy_t('help_rating'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        null=True,
        verbose_name=lazy_t('f_created_at'),
        help_text=lazy_t('help_created_at'),
    )

    objects = models.Manager()
    active = ActiveManager()

    def __str__(self):
        return self.name

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def stock_state(self):
        """'out' / 'low' / 'ok' - what counts as low depends on the price
        (see store/stock_rules.py)."""
        from .stock_rules import effective_price, stock_state
        return stock_state(self.stock, effective_price(self.price, self.is_sale, self.sale_price))

    class Meta:
        verbose_name = lazy_t('admin_model_product')
        verbose_name_plural = lazy_t('admin_products')


HERO_MAX_SLIDES = 5           # the home page slider never holds more than this
HERO_SIZE = (1600, 600)       # every slide image is stored at exactly this size (8:3)
HERO_MIN_SIZE = (1200, 450)   # smallest picture we accept (it would look blurry below this)
HERO_MAX_UPLOAD_MB = 5


def _normalize_banner(uploaded):
    """Turn whatever was uploaded into a 1600x600 JPEG of fixed quality, so
    every slide has the same size and sharpness no matter what the admin
    picked. (The admin form already checked the 8:3 shape, so nothing
    important gets cropped here.)"""
    import os
    from io import BytesIO

    from django.core.files.base import ContentFile
    from PIL import Image, ImageOps

    uploaded.seek(0)
    img = ImageOps.exif_transpose(Image.open(uploaded))
    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
        img = img.convert('RGBA')
        flat = Image.new('RGB', img.size, (255, 255, 255))
        flat.paste(img, mask=img.split()[-1])
        img = flat
    else:
        img = img.convert('RGB')
    img = ImageOps.fit(img, HERO_SIZE, Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, 'JPEG', quality=88, optimize=True, progressive=True)
    name = os.path.splitext(os.path.basename(uploaded.name))[0] + '.jpg'
    return ContentFile(buf.getvalue(), name=name)


class HeroSlide(models.Model):
    """One slide of the home page slider (at most HERO_MAX_SLIDES).

    The admin picks a product and uploads a banner picture just for the
    slider. The picture is NOT the product's own photo, so its size and
    quality can be controlled. The slide's button opens the chosen product's
    detail page.
    """

    POSITION_CHOICES = [
        ('left', lazy_t('hero_pos_left')),
        ('center', lazy_t('hero_pos_center')),
        ('right', lazy_t('hero_pos_right')),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='hero_slides',
        verbose_name=lazy_t('hero_f_product'),
        help_text=lazy_t('help_hero_product'),
    )
    image = models.ImageField(
        upload_to='uploads/hero/',
        verbose_name=lazy_t('hero_f_image'),
        help_text=lazy_t('help_hero_image'),
    )
    button_text = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name=lazy_t('hero_f_button'),
        help_text=lazy_t('help_hero_button'),
    )
    button_position = models.CharField(
        max_length=10, choices=POSITION_CHOICES, default='left',
        verbose_name=lazy_t('hero_f_button_pos'),
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=lazy_t('hero_f_order'),
        help_text=lazy_t('help_hero_order'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=lazy_t('admin_col_is_active'),
        help_text=lazy_t('help_hero_active'),
    )

    def __str__(self):
        return self.product.name

    def clean(self):
        from django.core.exceptions import ValidationError

        if self._state.adding and HeroSlide.objects.count() >= HERO_MAX_SLIDES:
            raise ValidationError(str(lazy_t('hero_err_max')).format(max=HERO_MAX_SLIDES))
        if self.product_id and not self.product.is_active:
            raise ValidationError({'product': str(lazy_t('hero_err_inactive'))})

    def save(self, *args, **kwargs):
        old_name = None
        if self.pk:
            old = HeroSlide.objects.filter(pk=self.pk).only('image').first()
            old_name = old.image.name if old and old.image else None
        if self.image and not self.image._committed:
            self.image = _normalize_banner(self.image)
        super().save(*args, **kwargs)
        # A replaced picture is not kept around.
        if old_name and old_name != self.image.name:
            self.image.storage.delete(old_name)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = lazy_t('hero_model')
        verbose_name_plural = lazy_t('hero_models')


class SearchHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    query = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.query

class ProductOption(models.Model):
    """A choice a customer must make before adding this product to the
    cart - not just colour, but any kind of variant a store might sell:
    ice-cream flavour, clothing size, phone storage capacity, whatever.

    Options are grouped by `option_type` (a free-text label you choose,
    e.g. "Flavor", "Size", "Color"). A product can have several groups at
    once, and each group can have several values (rows) - the customer
    picks one value per group from a dropdown on the product page. Values
    are shown as plain text (e.g. "Red", "Large") - there's no colour
    swatch UI, so "Color" is just another dropdown like any other.

    Managed as an inline on the Product admin page, so no separate menu
    item is needed. Stock is NOT split per option - Product.stock stays
    the single source of truth for how many units are available; this
    just records which combination the customer picked, on the order.
    """
    product = models.ForeignKey(Product, related_name='options', on_delete=models.CASCADE,
                                verbose_name=lazy_t('f_product'))
    option_type = models.CharField(
        max_length=50,
        default='Option',
        verbose_name=lazy_t('f_option_type'),
        help_text=lazy_t('help_option_type'),
    )
    value = models.CharField(
        max_length=50,
        verbose_name=lazy_t('f_option_value'),
        help_text=lazy_t('help_option_value'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=lazy_t('admin_col_is_active'),
        help_text=lazy_t('help_option_active'),
    )

    def __str__(self):
        return f"{self.product.name} - {self.option_type}: {self.value}"

    class Meta:
        verbose_name = lazy_t('admin_model_productoption')
        verbose_name_plural = lazy_t('admin_productoptions')
        ordering = ['option_type', 'id']


class StockEntry(models.Model):
    """One purchase / delivery of a product into the warehouse.

    Created every time stock is added on the Stock page. quantity x unit_cost
    is the money the shop spent (Зарлага) on that day, so the expense figure in
    Reports > Overview counts when goods are bought, not when they are sold.
    """
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_entries')
    name = models.CharField(max_length=100, blank=True, default='')   # product name at the time
    quantity = models.PositiveIntegerField(verbose_name=lazy_t('f_quantity'))
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                    verbose_name=lazy_t('f_unit_cost'))
    # True for the stock a product already had (or was created with) rather than
    # a later delivery. Its price follows the product's cost price (see ProductAdmin.save_model).
    is_opening = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name=lazy_t('f_created_at'))

    class Meta:
        ordering = ['-created_at']
        verbose_name = lazy_t('admin_model_stockentry')
        verbose_name_plural = lazy_t('admin_stockentries')

    def __str__(self):
        return f'{self.name or self.product_id} +{self.quantity}'

    @property
    def total_cost(self):
        return self.quantity * self.unit_cost
