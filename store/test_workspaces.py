"""Several job positions per person, and which site each one can open.

    customer            -> shop login (unchanged)
    Admin / Operator    -> admin site     (User.is_staff)
    Хүргэгч (Driver)    -> driver site    (active delivery.Driver)
    Admin + Хүргэгч     -> either, via a "which site?" screen after login
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from delivery.models import Driver

from .forms import EmployeeForm, EmployeeProfileForm
from .models import Customer, Employee, EmployeePosition
from .workspaces import get_workspaces

User = get_user_model()
PASSWORD = 'Zx9!kLm2#qWe'
ADMIN, OPERATOR, DRIVER = 'Admin', 'Operator', 'Хүргэгч'


def appoint(username, positions):
    """Create a person the way the real "add employee" form does."""
    form = EmployeeForm({
        'username': username, 'email': f'{username}@example.mn', 'phone': '99112233',
        'password1': PASSWORD, 'password2': PASSWORD, 'positions': positions,
    })
    assert form.is_valid(), form.errors
    return form.save()


def reposition(user, positions):
    Employee.objects.get(user=user).set_positions(positions)
    return User.objects.get(pk=user.pk)


def keys(user):
    return [w.key for w in get_workspaces(User.objects.get(pk=user.pk))]


class AppointingPositionsTests(TestCase):
    def test_admin_only(self):
        user = appoint('boss', [ADMIN])
        self.assertTrue(user.is_staff)
        self.assertFalse(Driver.objects.filter(user=user).exists())
        self.assertEqual(keys(user), ['admin'])

    def test_driver_only_is_not_staff(self):
        user = appoint('dan', [DRIVER])
        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertTrue(Driver.objects.get(user=user).is_active)
        self.assertEqual(keys(user), ['driver'])
        self.assertFalse(Customer.objects.filter(user=user).exists())

    def test_two_positions_give_two_sites(self):
        user = appoint('both', [ADMIN, DRIVER])
        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(Driver.objects.get(user=user).is_active)
        self.assertEqual(keys(user), ['admin', 'driver'])
        employee = Employee.objects.get(user=user)
        self.assertEqual(sorted(employee.position_list), sorted([ADMIN, DRIVER]))
        self.assertEqual(employee.position, 'Admin, Хүргэгч')       # readable summary of the old column

    def test_at_least_one_position_is_required(self):
        form = EmployeeForm({'username': 'x', 'email': 'x@x.mn', 'password1': PASSWORD,
                             'password2': PASSWORD, 'positions': []})
        self.assertFalse(form.is_valid())
        self.assertIn('positions', form.errors)

    def test_adding_a_second_position_later(self):
        user = appoint('later', [ADMIN])
        user = reposition(user, [ADMIN, DRIVER])
        self.assertEqual(keys(user), ['admin', 'driver'])

    def test_removing_driver_keeps_admin_and_the_login(self):
        user = appoint('both', [ADMIN, DRIVER])
        user = reposition(user, [ADMIN])
        self.assertTrue(user.is_active)
        self.assertEqual(keys(user), ['admin'])
        self.assertFalse(Driver.objects.get(user=user).is_active)
        self.assertTrue(Employee.objects.get(user=user).is_active)

    def test_removing_admin_keeps_driver(self):
        user = appoint('both', [ADMIN, DRIVER])
        user = reposition(user, [DRIVER])
        self.assertFalse(user.is_staff)
        self.assertEqual(keys(user), ['driver'])

    def test_driver_position_can_come_back(self):
        user = appoint('flip', [ADMIN, DRIVER])
        reposition(user, [ADMIN])
        user = reposition(user, [ADMIN, DRIVER])
        self.assertEqual(keys(user), ['admin', 'driver'])
        self.assertEqual(Driver.objects.filter(user=user).count(), 1)

    def test_superuser_is_never_demoted(self):
        boss = User.objects.create_superuser('root', 'r@x.mn', PASSWORD)
        employee = Employee.objects.get(user=boss)
        employee.set_positions([DRIVER])
        boss.refresh_from_db()
        self.assertTrue(boss.is_staff)
        self.assertTrue(boss.is_superuser)

    def test_label_only_position_never_removes_admin_access(self):
        """An old row that just says "Employee" must not lock a staff member out."""
        user = User.objects.create_user('old', password=PASSWORD, is_staff=True)
        employee = Employee.objects.get(user=user)
        employee.set_positions(['Employee'])
        user.refresh_from_db()
        self.assertTrue(user.is_staff)

    def test_old_names_are_understood(self):
        """Old rows / imports may say "Админ" or "Courier"; they are stored under the standard names."""
        user = appoint('names', [OPERATOR])
        Employee.objects.get(user=user).set_positions(['Админ', 'Courier'])
        self.assertEqual(sorted(Employee.objects.get(user=user).position_list), sorted([ADMIN, DRIVER]))
        self.assertEqual(keys(user), ['admin', 'driver'])

    def test_employee_who_left_cannot_log_in_anywhere(self):
        user = appoint('gone', [ADMIN, DRIVER])
        employee = Employee.objects.get(user=user)
        employee.is_active = False
        employee.save()
        self.assertEqual(keys(user), [])
        self.assertFalse(self.client.login(username='gone', password=PASSWORD))

    def test_pure_driver_deactivation_still_blocks_login(self):
        """Behaviour from before this change: switching a driver off blocks their login."""
        user = appoint('dan', [DRIVER])
        driver = Driver.objects.get(user=user)
        driver.is_active = False
        driver.save()
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        driver.is_active = True
        driver.save()
        user.refresh_from_db()
        self.assertTrue(user.is_active)


class LoginRoutingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user('cust', password=PASSWORD)
        cls.admin = appoint('adm', [ADMIN])
        cls.driver = appoint('drv', [DRIVER])
        cls.both = appoint('both', [ADMIN, DRIVER])

    def login(self, where, username, **extra):
        data = {'username': username, 'password': PASSWORD}
        if where == 'admin:login':
            # the admin login form carries this hidden field, so a browser always sends it
            data['next'] = reverse('admin:index')
        return self.client.post(reverse(where), {**data, **extra})

    # --- shop login: customers unchanged ---------------------------------
    def test_customer_login_is_unchanged(self):
        resp = self.login('login', 'cust')
        self.assertRedirects(resp, reverse('home'), fetch_redirect_response=False)

    def test_shop_login_sends_single_role_staff_to_their_site(self):
        self.assertRedirects(self.login('login', 'adm'), reverse('admin:index'), fetch_redirect_response=False)
        self.client.logout()
        self.assertRedirects(self.login('login', 'drv'), reverse('delivery:board'), fetch_redirect_response=False)

    def test_shop_login_two_positions_goes_to_chooser(self):
        self.assertRedirects(self.login('login', 'both'), reverse('choose_workspace'), fetch_redirect_response=False)

    # --- admin login -----------------------------------------------------
    def test_admin_login_single_role_goes_to_admin(self):
        self.assertRedirects(self.login('admin:login', 'adm'), reverse('admin:index'), fetch_redirect_response=False)

    def test_admin_login_two_positions_goes_to_chooser(self):
        self.assertRedirects(self.login('admin:login', 'both'), reverse('choose_workspace'), fetch_redirect_response=False)

    def test_admin_login_keeps_deep_link(self):
        target = reverse('admin:store_product_changelist')
        resp = self.login('admin:login', 'both', next=target)
        self.assertRedirects(resp, target, fetch_redirect_response=False)

    def test_driver_cannot_use_admin_login(self):
        resp = self.login('admin:login', 'drv')
        self.assertEqual(resp.status_code, 200)               # form shown again, not signed in
        self.assertNotIn('_auth_user_id', self.client.session)

    # --- driver login ----------------------------------------------------
    def test_driver_login_single_role_goes_to_board(self):
        self.assertRedirects(self.login('delivery:login', 'drv'), reverse('delivery:board'), fetch_redirect_response=False)

    def test_driver_login_two_positions_goes_to_chooser(self):
        self.assertRedirects(self.login('delivery:login', 'both'), reverse('choose_workspace'), fetch_redirect_response=False)

    def test_driver_login_keeps_next(self):
        target = reverse('delivery:deliveries')
        resp = self.login('delivery:login', 'both', next=target)
        self.assertRedirects(resp, target, fetch_redirect_response=False)

    def test_admin_cannot_use_driver_login(self):
        resp = self.login('delivery:login', 'adm')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    # --- chooser ---------------------------------------------------------
    def test_chooser_lists_both_sites(self):
        self.client.force_login(self.both)
        resp = self.client.get(reverse('choose_workspace'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse('admin:index'))
        self.assertContains(resp, reverse('delivery:board'))

    def test_chooser_skips_itself_for_one_site(self):
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.get(reverse('choose_workspace')), reverse('admin:index'),
                             fetch_redirect_response=False)

    def test_chooser_for_customer_goes_home(self):
        self.client.force_login(self.customer)
        self.assertRedirects(self.client.get(reverse('choose_workspace')), reverse('home'),
                             fetch_redirect_response=False)

    def test_chooser_needs_login(self):
        resp = self.client.get(reverse('choose_workspace'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('login'), resp['Location'])

    # --- one session, two sites: switching needs no second login ---------
    def test_one_login_opens_both_sites(self):
        self.client.force_login(self.both)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)
        self.assertEqual(self.client.get(reverse('delivery:dashboard')).status_code, 200)

    def test_switch_link_shown_only_to_people_with_two_sites(self):
        chooser = reverse('choose_workspace')
        self.client.force_login(self.both)
        self.assertContains(self.client.get(reverse('admin:index')), chooser)
        self.assertContains(self.client.get(reverse('delivery:dashboard')), chooser)
        self.client.force_login(self.driver)
        self.assertNotContains(self.client.get(reverse('delivery:dashboard')), chooser)
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get(reverse('admin:index')), chooser)

    def test_driver_role_switched_off_closes_driver_site_only(self):
        reposition(self.both, [ADMIN])
        self.client.force_login(User.objects.get(pk=self.both.pk))
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)
        self.assertRedirects(self.client.get(reverse('delivery:dashboard')),
                             reverse('delivery:login'), fetch_redirect_response=False)
        reposition(self.both, [ADMIN, DRIVER])              # put it back for the other tests


class PositionSecurityTests(TestCase):
    def test_profile_form_cannot_change_positions(self):
        """Positions decide who gets into the admin site, so an employee must not edit their own."""
        form = EmployeeProfileForm()
        self.assertNotIn('position', form.fields)
        self.assertEqual(list(form.fields), ['phone'])

    def test_profile_post_cannot_make_someone_admin(self):
        user = appoint('cashier', [DRIVER])
        self.client.force_login(user)
        self.client.post(reverse('profile'), {'phone': '88001122', 'position': ADMIN, 'positions': [ADMIN]})
        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertEqual(Employee.objects.get(user=user).position_list, [DRIVER])

    def test_employee_pages_are_staff_only(self):
        driver = appoint('drv', [DRIVER])
        self.client.force_login(driver)
        resp = self.client.get(reverse('add_employee'))
        self.assertEqual(resp.status_code, 302)       # not staff -> bounced to login

    def test_admin_change_form_sets_positions(self):
        boss = User.objects.create_superuser('root', 'r@x.mn', PASSWORD)
        person = appoint('adm', [ADMIN])
        employee = Employee.objects.get(user=person)
        self.client.force_login(boss)
        url = reverse('admin:store_employee_change', args=[employee.pk])
        resp = self.client.post(url, {'user': person.pk, 'positions': [ADMIN, DRIVER],
                                      'phone': '99112233', 'is_active': 'on'})
        self.assertEqual(resp.status_code, 302, getattr(resp, 'context', None) and resp.context['adminform'].form.errors)
        self.assertEqual(keys(person), ['admin', 'driver'])

        resp = self.client.post(url, {'user': person.pk, 'positions': [DRIVER],
                                      'phone': '99112233', 'is_active': 'on'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(keys(person), ['driver'])

    def test_admin_change_form_shows_current_positions_ticked(self):
        boss = User.objects.create_superuser('root', 'r@x.mn', PASSWORD)
        person = appoint('both', [ADMIN, DRIVER])
        self.client.force_login(boss)
        resp = self.client.get(reverse('admin:store_employee_change', args=[Employee.objects.get(user=person).pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(sorted(resp.context['adminform'].form.initial['positions']), sorted([ADMIN, DRIVER]))

    def test_employees_page_lists_every_position(self):
        boss = User.objects.create_superuser('root', 'r@x.mn', PASSWORD)
        appoint('both', [ADMIN, DRIVER])
        self.client.force_login(boss)
        resp = self.client.get(reverse('employees'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Админ, Хүргэгч')
