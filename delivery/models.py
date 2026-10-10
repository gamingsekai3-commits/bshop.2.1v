from django.conf import settings
from django.db import models
from django.utils import timezone

from store.models import ActiveManager
from store.translations import lazy_t


class Driver(models.Model):
    """Хүргэгч. Django-ийн User-тэй 1-to-1 холбогдоно (Employee / Customer-тай ижил арга),
    тиймээс нэвтрэлт, нууц үг нь хэвээр Django auth-аар явна."""

    STATUS_ONLINE = 'online'
    STATUS_OFFLINE = 'offline'
    STATUS_BUSY = 'busy'
    STATUS_CHOICES = [
        (STATUS_ONLINE, lazy_t('dl_ds_online')),
        (STATUS_OFFLINE, lazy_t('dl_ds_offline')),
        (STATUS_BUSY, lazy_t('dl_ds_busy')),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='driver_profile',
        verbose_name=lazy_t('dl_f_user'),
    )
    phone = models.CharField(max_length=20, blank=True, default='', verbose_name=lazy_t('dl_f_phone'))
    # Soft delete: идэвхгүй болгоход нэвтрэх эрх хаагдана, хүргэлтийн түүх хэвээр үлдэнэ.
    is_active = models.BooleanField(default=True, verbose_name=lazy_t('dl_f_active'))
    is_online = models.BooleanField(default=False, verbose_name=lazy_t('dl_f_online'))
    current_status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_OFFLINE, verbose_name=lazy_t('dl_f_status'),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=lazy_t('dl_f_created'))

    objects = models.Manager()
    active = ActiveManager()

    class Meta:
        ordering = ['user__username']
        verbose_name = lazy_t('dl_model_driver')
        verbose_name_plural = lazy_t('dl_drivers')

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.username

    # NOTE: this used to copy is_active onto the login. A person can now hold
    # several positions (e.g. Admin + Хүргэгч), so switching only the driver
    # role off must not lock them out of everything. The login is switched by
    # the Employee row instead (see delivery/signals.py: a driver who is not
    # also staff still gets their login blocked, exactly as before).

    def refresh_status(self):
        """OFFLINE / BUSY / ONLINE-ийг is_online болон идэвхтэй хүргэлтээс тооцно."""
        if not self.is_online:
            status = self.STATUS_OFFLINE
        elif self.deliveries.filter(status__in=Delivery.ACTIVE_STATUSES).exists():
            status = self.STATUS_BUSY
        else:
            status = self.STATUS_ONLINE
        if status != self.current_status:
            self.current_status = status
            self.save(update_fields=['current_status'])
        return status


class Delivery(models.Model):
    PENDING = 'pending'
    ASSIGNED = 'assigned'
    ACCEPTED = 'accepted'
    PICKED_UP = 'picked_up'
    ON_THE_WAY = 'on_the_way'
    DELIVERED = 'delivered'
    FAILED = 'failed'
    CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (PENDING, lazy_t('dl_st_pending')),
        (ASSIGNED, lazy_t('dl_st_assigned')),
        (ACCEPTED, lazy_t('dl_st_accepted')),
        (PICKED_UP, lazy_t('dl_st_picked_up')),
        (ON_THE_WAY, lazy_t('dl_st_on_the_way')),
        (DELIVERED, lazy_t('dl_st_delivered')),
        (FAILED, lazy_t('dl_st_failed')),
        (CANCELLED, lazy_t('dl_st_cancelled')),
    ]

    # Хүргэгчийн гар дээр байгаа (дуусаагүй) төлвүүд.
    ACTIVE_STATUSES = (ASSIGNED, ACCEPTED, PICKED_UP, ON_THE_WAY)
    # Админ хүргэгчийг оноох / солих боломжтой төлвүүд (бараа гараас гараагүй үед).
    REASSIGNABLE_STATUSES = (PENDING, ASSIGNED, ACCEPTED, FAILED)

    FAIL_CUSTOMER_UNAVAILABLE = 'customer_unavailable'
    FAIL_WRONG_ADDRESS = 'wrong_address'
    FAIL_CUSTOMER_REFUSED = 'customer_refused'
    FAIL_PHONE_UNREACHABLE = 'phone_unreachable'
    FAIL_OTHER = 'other'
    FAILURE_CHOICES = [
        (FAIL_CUSTOMER_UNAVAILABLE, lazy_t('dl_fail_unavailable')),
        (FAIL_WRONG_ADDRESS, lazy_t('dl_fail_wrong_address')),
        (FAIL_CUSTOMER_REFUSED, lazy_t('dl_fail_refused')),
        (FAIL_PHONE_UNREACHABLE, lazy_t('dl_fail_phone')),
        (FAIL_OTHER, lazy_t('dl_fail_other')),
    ]

    order = models.OneToOneField(
        'cart.Order', on_delete=models.CASCADE, related_name='delivery', verbose_name=lazy_t('dl_f_order'),
    )
    driver = models.ForeignKey(
        Driver, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='deliveries', verbose_name=lazy_t('dl_f_driver'),
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING, verbose_name=lazy_t('dl_f_status'))
    delivery_address = models.TextField(verbose_name=lazy_t('dl_f_address'))
    district = models.CharField(max_length=100, blank=True, default='', verbose_name=lazy_t('dl_f_district'))
    phone = models.CharField(max_length=50, verbose_name=lazy_t('dl_f_phone'))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=lazy_t('dl_f_created'))
    assigned_at = models.DateTimeField(null=True, blank=True, verbose_name=lazy_t('dl_f_assigned'))
    accepted_at = models.DateTimeField(null=True, blank=True, verbose_name=lazy_t('dl_f_accepted'))
    picked_up_at = models.DateTimeField(null=True, blank=True, verbose_name=lazy_t('dl_f_picked_up'))
    on_the_way_at = models.DateTimeField(null=True, blank=True, verbose_name=lazy_t('dl_f_on_the_way'))
    # 2-р үе: замд яваа үед бараагаа буулгаж өгсөн цаг. Бүгд буусны дараа л 3-р үе (батлах) нээгдэнэ.
    unloaded_at = models.DateTimeField(null=True, blank=True, verbose_name='Буулгасан')
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name=lazy_t('dl_f_delivered'))
    failed_at = models.DateTimeField(null=True, blank=True, verbose_name=lazy_t('dl_f_failed_at'))

    failure_reason = models.CharField(
        max_length=30, choices=FAILURE_CHOICES, blank=True, default='', verbose_name=lazy_t('dl_f_fail_reason'),
    )
    note = models.TextField(blank=True, default='', verbose_name=lazy_t('dl_f_note'))

    class Meta:
        ordering = ['-created_at']
        verbose_name = lazy_t('dl_model_delivery')
        verbose_name_plural = lazy_t('dl_deliveries')

    def __str__(self):
        return f'Хүргэлт #{self.pk} (захиалга #{self.order_id})'

    @property
    def is_active_delivery(self):
        return self.status in self.ACTIVE_STATUSES


class DeliveryHistory(models.Model):
    """Хүргэлтийн төлөв / хүргэгч өөрчлөгдөх бүрт нэг мөр нэмнэ (өөрчлөхгүй, зөвхөн унших)."""

    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name='history', verbose_name=lazy_t('dl_f_delivery'))
    from_status = models.CharField(max_length=12, blank=True, default='', verbose_name=lazy_t('dl_f_from_status'))
    to_status = models.CharField(max_length=12, verbose_name=lazy_t('dl_f_to_status'))
    driver = models.ForeignKey(
        Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name=lazy_t('dl_f_driver'),
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name=lazy_t('dl_f_changed_by'),
    )
    note = models.CharField(max_length=255, blank=True, default='', verbose_name=lazy_t('dl_f_note'))
    created_at = models.DateTimeField(default=timezone.now, verbose_name=lazy_t('dl_f_date'))

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = lazy_t('dl_model_history')
        verbose_name_plural = lazy_t('dl_model_history')

    def __str__(self):
        return f'#{self.delivery_id}: {self.from_status or "-"} → {self.to_status}'