from django.conf import settings
from django.db import models
from django.utils import timezone

from store.models import ActiveManager, Product
from store.translations import lazy_t


class Order(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_DELIVERED = 'delivered'
    STATUS_CANCELLED = 'cancelled'
    # Delivery flow:  pending -> in delivery -> delivered
    #   Хүлээгдэж буй -> Хүргэлтэд авсан -> Хүргэлт дууссан
    # The middle step reuses the existing 'confirmed' value (so old rows and
    # reports keep working); STATUS_IN_DELIVERY is just its clearer name.
    STATUS_IN_DELIVERY = STATUS_CONFIRMED

    STATUS_CHOICES = [
        (STATUS_PENDING, lazy_t('status_pending')),
        (STATUS_CONFIRMED, lazy_t('status_confirmed')),
        (STATUS_DELIVERED, lazy_t('status_delivered')),
        (STATUS_CANCELLED, lazy_t('status_cancelled')),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name=lazy_t('f_user'),
    )
    name = models.CharField(max_length=200, verbose_name=lazy_t('customer_name'))
    phone = models.CharField(max_length=50, verbose_name=lazy_t('customer_phone'))
    address = models.TextField(verbose_name=lazy_t('f_address'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
                              verbose_name=lazy_t('f_status'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=lazy_t('f_created_at'))
    # Delivery. `courier` is whoever took (or was given) the order; it is set
    # together with status 'in delivery', so one order can never have two
    # couriers. Being assigned / taking an order is NOT income - income is only
    # booked once status reaches 'delivered' (see delivered_at).
    courier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deliveries',
        verbose_name=lazy_t('f_courier'),
    )
    picked_at = models.DateTimeField(null=True, blank=True, verbose_name=lazy_t('f_picked_at'))
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name=lazy_t('f_delivered_at'))
    # Soft delete / archive. `status` is where the order is in its life
    # (pending -> confirmed -> delivered), which is a different question from
    # whether the record should still be listed at all. Switching this off
    # hides the order from "My orders" instead of deleting it, so the sales
    # figures on the dashboard stay correct.
    is_active = models.BooleanField(
        default=True,
        verbose_name=lazy_t('admin_col_is_active'),
        help_text=lazy_t('help_order_active'),
    )

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = lazy_t('admin_model_order')
        verbose_name_plural = lazy_t('admin_orders')

    def __str__(self):
        return f"{lazy_t('admin_order_label')} #{self.id} ({self.get_status_display()})"

    def get_total_price(self):
        return sum(item.get_total_price() for item in self.items.all())

    def _sync_delivery_fields(self):
        """Keep courier / timestamps consistent with `status`.
        Returns the names of the fields it touched."""
        changed = set()
        now = timezone.now()
        if self.courier_id and self.status == self.STATUS_PENDING:
            # Giving a pending order a courier takes it out of the pool.
            self.status = self.STATUS_IN_DELIVERY
            changed.add('status')
        if self.status == self.STATUS_IN_DELIVERY and self.courier_id and not self.picked_at:
            self.picked_at = now
            changed.add('picked_at')
        if self.status == self.STATUS_DELIVERED:
            if not self.delivered_at:
                self.delivered_at = now
                changed.add('delivered_at')
        elif self.delivered_at is not None:
            # Re-opened by an admin: it is no longer income.
            self.delivered_at = None
            changed.add('delivered_at')
        if self.status == self.STATUS_PENDING and self.picked_at is not None:
            self.picked_at = None
            changed.add('picked_at')
        return changed

    def save(self, *args, **kwargs):
        changed = self._sync_delivery_fields()
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and changed:
            kwargs['update_fields'] = set(update_fields) | changed
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE,
                              verbose_name=lazy_t('f_order'))
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True,
                                verbose_name=lazy_t('f_product'))
    price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name=lazy_t('f_price'))
    quantity = models.PositiveIntegerField(verbose_name=lazy_t('f_quantity'))
    name = models.CharField(max_length=255, blank=True, default='', verbose_name=lazy_t('admin_col_name'))
    options = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name=lazy_t('table_options'),
        help_text=lazy_t('help_order_item_options'),
    )

    class Meta:
        verbose_name = lazy_t('admin_model_orderitem')
        verbose_name_plural = lazy_t('admin_order_items')

    def get_total_price(self):
        return self.price * self.quantity