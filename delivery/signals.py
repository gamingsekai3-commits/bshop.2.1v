from django.db.models.signals import post_save
from django.dispatch import receiver

from .services import create_delivery_for_order


@receiver(post_save, sender='cart.Order')
def order_created(sender, instance, created, **kwargs):
    """Шинэ захиалга бүрт хүргэлт (PENDING) автоматаар үүснэ.
    cart/views.py-д ямар ч өөрчлөлт хэрэггүй."""
    if created:
        create_delivery_for_order(instance)


DRIVER_POSITION = 'Хүргэгч'   # store.forms.POSITION_CHOICES-ийн утгатай ижил


@receiver(post_save, sender='delivery.Driver')
def driver_to_employee(sender, instance, **kwargs):
    """Хүргэгч бүр store-ийн Ажилтны жагсаалтад (Employee, албан тушаал = Хүргэгч) орно.
    Хүргэгчийн утас, идэвхтэй эсэх өөрчлөгдөхөд Ажилтны мөр дагаж шинэчлэгдэнэ.
    Нэвтрэх эрх (is_staff) өөрчлөгдөхгүй тул хүргэгч админ руу орохгүй."""
    from store.models import Employee

    employee, created = Employee.objects.get_or_create(
        user=instance.user,
        defaults={'position': DRIVER_POSITION, 'phone': instance.phone, 'is_active': instance.is_active},
    )
    if created:
        return
    changed = []
    if employee.phone != instance.phone:
        employee.phone = instance.phone
        changed.append('phone')
    if employee.is_active != instance.is_active:
        employee.is_active = instance.is_active
        changed.append('is_active')
    if changed:
        employee.save(update_fields=changed)