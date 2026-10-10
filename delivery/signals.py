from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Driver
from .services import create_delivery_for_order


@receiver(post_save, sender='cart.Order')
def order_created(sender, instance, created, **kwargs):
    """Шинэ захиалга бүрт хүргэлт (PENDING) автоматаар үүснэ.
    cart/views.py-д ямар ч өөрчлөлт хэрэггүй."""
    if created:
        create_delivery_for_order(instance)


DRIVER_POSITION = 'Хүргэгч'   # store.models.POSITION_DRIVER-тэй ижил


@receiver(post_save, sender='delivery.Driver')
def driver_to_employee(sender, instance, **kwargs):
    """Хүргэгч бүр store-ийн Ажилтны жагсаалтад (Employee) орж, "Хүргэгч" албан тушаалтай болно.

    * Хүргэгчийн утас өөрчлөгдөхөд Ажилтны мөр дагаж шинэчлэгдэнэ.
    * Зөвхөн хүргэгч (админ эрхгүй) хүнийг идэвхгүй болговол нэвтрэх эрх нь хаагдана (өмнөх шигээ).
      Харин админ эрхтэй хүнд хүргэгчийн үүргийг унтраахад нэвтрэх эрх нь хаагдахгүй, зөвхөн
      хүргэгчийн сайт хаагдана.
    * is_staff өөрчлөгдөхгүй тул хүргэгч админ руу орохгүй.
    """
    from django.contrib.auth import get_user_model
    from store.models import Employee, EmployeePosition

    user_is_staff = get_user_model().objects.filter(pk=instance.user_id, is_staff=True).exists()
    employee, created = Employee.objects.get_or_create(
        user=instance.user,
        defaults={'position': DRIVER_POSITION, 'phone': instance.phone, 'is_active': instance.is_active},
    )
    if not created:
        changed = []
        if employee.phone != instance.phone:
            employee.phone = instance.phone
            changed.append('phone')
        if employee.is_active != instance.is_active and not user_is_staff:
            employee.is_active = instance.is_active
            changed.append('is_active')
        if changed:
            employee.save(update_fields=changed)

    # The "Хүргэгч" position mirrors "driver role is switched on".
    if instance.is_active:
        EmployeePosition.objects.get_or_create(employee=employee, position=DRIVER_POSITION)
    else:
        EmployeePosition.objects.filter(employee=employee, position=DRIVER_POSITION).delete()


def _sync_driver_role(sender, instance, **kwargs):
    """Admin ticks / unticks "Хүргэгч" on the employee form -> the driver
    profile is created or switched on / off to match."""
    from store.models import Employee, EmployeePosition, canonical_position

    if canonical_position(instance.position) != DRIVER_POSITION:
        return
    employee = Employee.objects.select_related('user').filter(pk=instance.employee_id).first()
    if employee is None:                      # the employee row is being deleted
        return
    wants = EmployeePosition.objects.filter(employee=employee, position=DRIVER_POSITION).exists()
    driver = Driver.objects.filter(user_id=employee.user_id).first()
    if wants:
        if driver is None:
            Driver.objects.create(user=employee.user, phone=(employee.phone or '')[:20], is_active=True)
        elif not driver.is_active:
            driver.is_active = True
            driver.save()
    elif driver is not None and driver.is_active:
        driver.is_active = False
        driver.save()


post_save.connect(_sync_driver_role, sender='store.EmployeePosition', dispatch_uid='dl_position_saved')
post_delete.connect(_sync_driver_role, sender='store.EmployeePosition', dispatch_uid='dl_position_deleted')
