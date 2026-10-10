"""Хүргэлтийн бүх төлөв өөрчлөлт энд нэг газар явна (admin ч, хүргэгчийн app ч).

Мөр бүрийг select_for_update-ээр түгжиж шалгадаг тул хоёр хүн зэрэг дарсан ч
төлөв дараалал алдагдахгүй.
"""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from store.translations import lazy_t

from .models import Delivery, DeliveryHistory, Driver


class DeliveryError(Exception):
    """Хэрэглэгчид шууд харуулж болох алдаа."""


# action -> (өмнөх төлөв, шинэ төлөв, цагийн талбар)
ACTIONS = {
    'accept': (Delivery.ASSIGNED, Delivery.ACCEPTED, 'accepted_at'),
    'pickup': (Delivery.ACCEPTED, Delivery.PICKED_UP, 'picked_up_at'),
    'depart': (Delivery.PICKED_UP, Delivery.ON_THE_WAY, 'on_the_way_at'),
    'deliver': (Delivery.ON_THE_WAY, Delivery.DELIVERED, 'delivered_at'),
    'fail': (Delivery.ON_THE_WAY, Delivery.FAILED, 'failed_at'),
}


def _log(delivery, from_status, to_status, by=None, note=''):
    DeliveryHistory.objects.create(
        delivery=delivery, from_status=from_status, to_status=to_status,
        driver=delivery.driver, changed_by=by, note=str(note)[:255],
    )


def create_delivery_for_order(order):
    """Захиалга бүрт нэг хүргэлт (PENDING). Давхар дуудагдсан ч нэгийг л үүсгэнэ."""
    delivery, created = Delivery.objects.get_or_create(
        order=order,
        defaults={'delivery_address': order.address, 'phone': order.phone},
    )
    if created:
        _log(delivery, '', Delivery.PENDING, note='Захиалгаас автоматаар үүссэн')
    return delivery


def set_driver(delivery, driver, by=None):
    """Админ хүргэгч онооно / солино / хасна. Бараа гараас гарсан хойно солихгүй."""
    if driver is not None and not driver.is_active:
        raise DeliveryError(lazy_t('dl_e_inactive_driver'))

    with transaction.atomic():
        # Re-read the row under a lock: the caller's object can be stale (the
        # driver may have picked the goods up since it was loaded).
        current = Delivery.objects.select_for_update().get(pk=delivery.pk)
        if current.status not in Delivery.REASSIGNABLE_STATUSES:
            raise DeliveryError(lazy_t('dl_e_no_reassign'))
        if driver == current.driver:
            return delivery
        old_driver = current.driver
        old_status = current.status
        delivery.refresh_from_db()
        delivery.driver = driver
        delivery.accepted_at = None
        delivery.unloaded_at = None
        if driver is None:
            delivery.status = Delivery.PENDING
            delivery.assigned_at = None
            note = 'Хүргэгчийг хассан'
        else:
            delivery.status = Delivery.ASSIGNED
            delivery.assigned_at = timezone.now()
            delivery.failure_reason = ''
            delivery.failed_at = None
            note = f'Хүргэгч оноосон: {driver.display_name}'
            if old_driver:
                note = f'Хүргэгч солисон: {old_driver.display_name} → {driver.display_name}'
            order = delivery.order
            if order.status == order.STATUS_PENDING:
                order.status = order.STATUS_CONFIRMED
                order.save(update_fields=['status'])
        delivery.save()
        _log(delivery, old_status, delivery.status, by=by, note=note)

    for d in (old_driver, driver):
        if d:
            d.refresh_status()
    return delivery


def cancel(delivery, by=None):
    if delivery.status not in Delivery.ACTIVE_STATUSES + (Delivery.PENDING,):
        raise DeliveryError(lazy_t('dl_e_no_cancel'))
    old_status = delivery.status
    with transaction.atomic():
        delivery.status = Delivery.CANCELLED
        delivery.save(update_fields=['status'])
        _log(delivery, old_status, Delivery.CANCELLED, by=by, note='Цуцалсан')
    if delivery.driver:
        delivery.driver.refresh_status()
    return delivery


def advance(delivery_id, driver, action, reason='', note=''):
    """Хүргэгч өөрийн хүргэлтийн төлвийг нэг алхам урагшлуулна."""
    if action not in ACTIONS:
        raise DeliveryError(lazy_t('dl_e_bad_action'))
    required, target, stamp = ACTIONS[action]

    with transaction.atomic():
        # Зөвхөн энэ хүргэгчид оноогдсон мөр. Өөр хүнийх бол DoesNotExist (view дээр 404).
        delivery = (
            Delivery.objects.select_for_update(of=('self',))
            .select_related('order')
            .get(pk=delivery_id, driver=driver)
        )
        if delivery.status != required:
            raise DeliveryError(lazy_t('dl_e_state_changed'))

        if action == 'fail':
            if reason not in dict(Delivery.FAILURE_CHOICES):
                raise DeliveryError(lazy_t('dl_e_reason'))
            delivery.failure_reason = reason
            if note:
                delivery.note = note
        elif note:
            delivery.note = note

        delivery.status = target
        setattr(delivery, stamp, timezone.now())
        if target in (Delivery.DELIVERED, Delivery.FAILED) and not delivery.unloaded_at:
            delivery.unloaded_at = delivery.on_the_way_at or timezone.now()
        delivery.save()

        if target == Delivery.DELIVERED:
            order = delivery.order
            order.status = order.STATUS_DELIVERED
            order.save(update_fields=['status'])

        log_note = dict(Delivery.FAILURE_CHOICES).get(reason, '') if action == 'fail' else ''
        _log(delivery, required, target, by=driver.user, note=log_note or note)

    driver.refresh_status()
    return delivery


# ---------------------------------------------------------------------------
# 3 үе шаттай урсгал (том машин: олон захиалгыг нэг дор авч явна)
#   1. Агуулхаас авах   : ASSIGNED          -> PICKED_UP
#   2. Замд гарах       : PICKED_UP         -> ON_THE_WAY, дараа нь бараагаа сонгож буулгана (unloaded_at)
#   3. Хүргэснийг батлах: ON_THE_WAY (бүгд буусан) -> DELIVERED / FAILED  (захиалгын ID-аар)
# ---------------------------------------------------------------------------

def _bulk_move(driver, ids, source, target, stamps, note):
    """Хүргэгчийн өөрийн, `source` төлөвтэй хүргэлтүүдийг нэг дор `target` руу шилжүүлнэ.
    Буцаах утга: шилжсэн хүргэлтийн тоо."""
    ids = [int(i) for i in ids]
    if not ids:
        raise DeliveryError('Захиалга сонгоно уу.')
    moved = 0
    with transaction.atomic():
        rows = list(
            Delivery.objects.select_for_update(of=('self',))
            .select_related('order')
            .filter(pk__in=ids, driver=driver, status=source)
        )
        now = timezone.now()
        for delivery in rows:
            delivery.status = target
            for field in stamps:
                if not getattr(delivery, field):
                    setattr(delivery, field, now)
            delivery.save()
            _log(delivery, source, target, by=driver.user, note=note)
            moved += 1
    if not moved:
        raise DeliveryError(lazy_t('dl_e_state_changed'))
    driver.refresh_status()
    return moved


def ensure_deliveries():
    """Delivery-гүй (app нэмэгдэхээс өмнөх) захиалгуудад PENDING хүргэлт үүсгэнэ."""
    from cart.models import Order
    orders = Order.objects.filter(
        delivery__isnull=True, is_active=True, courier__isnull=True,
    ).exclude(status__in=[Order.STATUS_CANCELLED, Order.STATUS_DELIVERED])
    for order in orders:
        create_delivery_for_order(order)


def receive_from_warehouse(driver, ids):
    """1-р үе: агуулхаас бараагаа авлаа.
    `ids` нь (а) надад оноогдсон ASSIGNED эсвэл (б) хүргэгчгүй PENDING хүргэлт байж болно -
    хүргэгч өөрөө авсан бол энэ мөрөнд түгжээд нэр дээрээ авна (хоёр хүн зэрэг авч болохгүй)."""
    ids = [int(i) for i in ids]
    if not ids:
        raise DeliveryError('Захиалга сонгоно уу.')
    if not driver.is_active:
        raise DeliveryError(lazy_t('dl_e_inactive_driver'))
    moved = 0
    with transaction.atomic():
        rows = list(
            Delivery.objects.select_for_update(of=('self',)).select_related('order')
            .filter(pk__in=ids)
            .filter(Q(driver=driver, status=Delivery.ASSIGNED) | Q(driver__isnull=True, status=Delivery.PENDING))
        )
        now = timezone.now()
        for delivery in rows:
            old_status = delivery.status
            delivery.driver = driver
            delivery.status = Delivery.PICKED_UP
            delivery.assigned_at = delivery.assigned_at or now
            delivery.accepted_at = now
            delivery.picked_up_at = now
            delivery.unloaded_at = None
            delivery.save()
            order = delivery.order
            if order.status == order.STATUS_PENDING:
                order.status = order.STATUS_CONFIRMED
                order.save(update_fields=['status'])
            note = 'Агуулхаас авсан' if old_status == Delivery.ASSIGNED else 'Хүргэгч өөрөө авсан'
            _log(delivery, old_status, Delivery.PICKED_UP, by=driver.user, note=note)
            moved += 1
    if not moved:
        raise DeliveryError('Эдгээр захиалгыг өөр хүргэгч аль хэдийн авсан байна.')
    driver.refresh_status()
    return moved


def depart(driver, ids):
    """2-р үе: замд гарлаа."""
    return _bulk_move(driver, ids, Delivery.PICKED_UP, Delivery.ON_THE_WAY,
                      ('on_the_way_at',), 'Замд гарсан')


def unload(driver, ids):
    """2-р үе (замд яваа): сонгосон захиалгын барааг буулгаж өглөө.
    Бүх бараа буусны дараа л 3-р үе (хүргэснийг батлах) нээгдэнэ."""
    ids = [int(i) for i in ids]
    if not ids:
        raise DeliveryError('Захиалга сонгоно уу.')
    moved = 0
    with transaction.atomic():
        rows = list(
            Delivery.objects.select_for_update(of=('self',))
            .select_related('order')
            .filter(pk__in=ids, driver=driver, status=Delivery.ON_THE_WAY, unloaded_at__isnull=True)
        )
        now = timezone.now()
        for delivery in rows:
            delivery.unloaded_at = now
            delivery.save(update_fields=['unloaded_at'])
            _log(delivery, Delivery.ON_THE_WAY, Delivery.ON_THE_WAY, by=driver.user, note='Бараа буулгасан')
            moved += 1
    if not moved:
        raise DeliveryError(lazy_t('dl_e_state_changed'))
    return moved


def pending_unload_count(driver):
    """Хүргэгчийн гар дээрх, бараа нь хараахан буугаагүй захиалгын тоо (авсан + замд яваа)."""
    return Delivery.objects.filter(
        driver=driver, status__in=(Delivery.PICKED_UP, Delivery.ON_THE_WAY), unloaded_at__isnull=True,
    ).count()


def confirm_by_order_id(driver, order_id, result='deliver', reason='', note=''):
    """3-р үе: захиалгын ID-аар хүргэсэн / амжилтгүйг батлах.
    Бүх бараа буулгагдсаны дараа л батлагдана."""
    try:
        order_id = int(str(order_id).strip().lstrip('#'))
    except (TypeError, ValueError):
        raise DeliveryError('Захиалгын ID буруу байна.')
    try:
        delivery = Delivery.objects.only('pk').get(order_id=order_id, driver=driver)
    except Delivery.DoesNotExist:
        raise DeliveryError(f'#{order_id} захиалга танд оноогдоогүй байна.')
    if pending_unload_count(driver):
        raise DeliveryError('Эхлээд бүх барааг буулгаж өгсөн гэж тэмдэглэнэ үү (2-р үе).')
    return advance(delivery.pk, driver, 'deliver' if result == 'deliver' else 'fail',
                   reason=reason, note=note)