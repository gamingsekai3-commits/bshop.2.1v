"""Which "sites" (workspaces) a signed-in person is allowed to open.

There are two staff sites besides the public shop:

    admin  -> /admin/      needs User.is_staff
    driver -> /delivery/   needs an active delivery.Driver profile

Staff (admins, drivers, any employee) sign in ONLY through the "Work Web" login
(/work/). The customer login (/login/) refuses them - see is_work_user().

Access always comes from those real flags, never from the free-text position
label. The positions an admin ticks on the employee form are what *set* the
flags (see Employee.refresh_from_positions and delivery/signals.py).

Customers have no staff workspace; they keep using the normal shop login.
"""
from dataclasses import dataclass

from django.shortcuts import redirect
from django.urls import reverse

from .translations import lazy_t

ADMIN = 'admin'
DRIVER = 'driver'

# URL name of the one login page for admins, drivers and employees.
WORK_LOGIN = 'work_login'


@dataclass(frozen=True)
class Workspace:
    key: str
    label: object          # lazy translated text
    url_name: str          # where the site starts (after login)
    login_url_name: str    # where an anonymous visitor is sent to sign in


_WORKSPACES = {
    ADMIN: Workspace(ADMIN, lazy_t('ws_admin'), 'admin:index', WORK_LOGIN),
    DRIVER: Workspace(DRIVER, lazy_t('ws_driver'), 'delivery:board', WORK_LOGIN),
}


def is_work_user(user):
    """True for anyone who belongs on Work Web instead of the customer login:
    admins / staff, superusers, drivers and every employee (even one whose
    position is only a label and opens no site).

    Reverse one-to-ones are read by name so store never imports delivery; a
    missing profile raises an AttributeError subclass, hence the getattr default.
    """
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_staff or user.is_superuser:
        return True
    if getattr(user, 'employee_profile', None) is not None:
        return True
    return getattr(user, 'driver_profile', None) is not None


def get_workspaces(user):
    """Workspaces this user may enter, admin first. Empty list = plain customer."""
    if not getattr(user, 'is_authenticated', False) or not user.is_active:
        return []
    found = []
    if user.is_staff:
        found.append(_WORKSPACES[ADMIN])
    # delivery is a separate app; the reverse one-to-one is read by name so
    # store never imports it (a missing profile raises an AttributeError subclass).
    driver = getattr(user, 'driver_profile', None)
    if driver is not None and driver.is_active:
        found.append(_WORKSPACES[DRIVER])
    return found


def workspace_url(workspace):
    return reverse(workspace.url_name)


def landing_redirect(user):
    """Where to send someone right after they sign in.

    no staff workspace -> the shop home page (customers: unchanged)
    exactly one        -> straight into that site
    two or more        -> the "which site?" chooser
    """
    spaces = get_workspaces(user)
    if not spaces:
        return redirect('home')
    if len(spaces) == 1:
        return redirect(workspace_url(spaces[0]))
    return redirect('choose_workspace')
