"""Who counts as a courier (хүргэгч).

A courier is an active user in the "Courier" group (or a superuser). The
admin makes someone a courier by adding them to that group on the user's
page in the admin panel - no extra table needed. The group itself is created
by delivery/migrations/0001_courier_group.py.
"""
from functools import wraps

from django.contrib.auth import get_user_model
from django.contrib.auth.views import redirect_to_login
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse

COURIER_GROUP = 'Courier'


def is_courier(user):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name=COURIER_GROUP).exists()


def active_couriers():
    """Users the admin may hand an order to."""
    return get_user_model().objects.filter(
        is_active=True, groups__name=COURIER_GROUP,
    ).order_by('username')


def courier_choices():
    """Active couriers, plus anyone already holding an order (so an order
    keeps its courier in the admin form even if they left the group)."""
    return get_user_model().objects.filter(
        Q(is_active=True, groups__name=COURIER_GROUP) | Q(deliveries__isnull=False)
    ).distinct().order_by('username')


def courier_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), reverse('delivery:login'))
        if not is_courier(request.user):
            return render(request, 'delivery/forbidden.html', status=403)
        return view(request, *args, **kwargs)
    return wrapper
