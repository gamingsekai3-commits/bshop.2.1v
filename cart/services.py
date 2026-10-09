"""Business rules for handing orders to couriers.

Kept out of the views / admin so the website and the admin panel use exactly
the same rules. Every function changes the order with ONE conditional UPDATE
(or under a row lock), so two couriers pressing "take" at the same moment can
never both get the order: the database lets only the first one through.
"""
from django.db import transaction
from django.utils import timezone

from .models import Order


def claim_order(order_id, courier):
    """A courier takes a pending order. True if it is theirs now, False if it
    was already taken / is no longer available."""
    updated = Order.objects.filter(
        pk=order_id,
        is_active=True,
        status=Order.STATUS_PENDING,
        courier__isnull=True,
    ).update(
        status=Order.STATUS_IN_DELIVERY,
        courier=courier,
        picked_at=timezone.now(),
    )
    return updated == 1


def complete_order(order_id, courier):
    """The courier who holds the order marks it delivered. Only now does it
    become income. True on success."""
    updated = Order.objects.filter(
        pk=order_id,
        is_active=True,
        status=Order.STATUS_IN_DELIVERY,
        courier=courier,
    ).update(
        status=Order.STATUS_DELIVERED,
        delivered_at=timezone.now(),
    )
    return updated == 1


def assign_orders(order_ids, courier):
    """Admin gives orders to a specific courier. Works on pending orders and
    on orders already in delivery (re-assign); delivered / cancelled /
    archived ones are left alone. Returns how many orders were assigned."""
    assigned = 0
    now = timezone.now()
    with transaction.atomic():
        orders = Order.objects.select_for_update().filter(
            pk__in=list(order_ids),
            is_active=True,
            status__in=[Order.STATUS_PENDING, Order.STATUS_IN_DELIVERY],
        )
        for order in orders:
            order.courier = courier
            order.status = Order.STATUS_IN_DELIVERY
            order.picked_at = now
            order.save()
            assigned += 1
    return assigned
