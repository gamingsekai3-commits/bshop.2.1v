from django.core.management.base import BaseCommand

from cart.models import Order
from delivery.services import create_delivery_for_order


class Command(BaseCommand):
    help = 'Хүргэлтгүй байгаа одоогийн захиалгуудад PENDING хүргэлт үүсгэнэ (нэг удаа ажиллуулахад хангалттай).'

    def handle(self, *args, **options):
        orders = Order.objects.filter(delivery__isnull=True, is_active=True).exclude(status__in=[Order.STATUS_CANCELLED, Order.STATUS_DELIVERED])
        count = 0
        for order in orders:
            create_delivery_for_order(order)
            count += 1
        self.stdout.write(self.style.SUCCESS(f'{count} хүргэлт үүслээ.'))
