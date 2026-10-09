from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cart.models import Order

from . import services
from .models import Delivery, Driver

User = get_user_model()


def make_driver(username='driver1', **kwargs):
    user = User.objects.create_user(username=username, password='pass12345!', first_name='Бат-Эрдэнэ')
    user.customer_profile.delete()
    return Driver.objects.create(user=user, phone='99112233', **kwargs)


def make_order():
    return Order.objects.create(name='Бат', phone='99112233', address='Баянзүрх, 26-р хороо')


class DeliveryFlowTests(TestCase):
    def setUp(self):
        self.driver = make_driver(is_online=True)
        self.order = make_order()
        self.delivery = self.order.delivery

    def test_order_creates_pending_delivery(self):
        self.assertEqual(self.delivery.status, Delivery.PENDING)
        self.assertEqual(self.delivery.delivery_address, 'Баянзүрх, 26-р хороо')
        self.assertEqual(self.delivery.history.count(), 1)

    def test_assign_then_full_workflow(self):
        services.set_driver(self.delivery, self.driver)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, Delivery.ASSIGNED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_CONFIRMED)

        for action in ('accept', 'pickup', 'depart', 'deliver'):
            services.advance(self.delivery.pk, self.driver, action)

        self.delivery.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.delivery.status, Delivery.DELIVERED)
        self.assertIsNotNone(self.delivery.delivered_at)
        self.assertEqual(self.order.status, Order.STATUS_DELIVERED)

    def test_cannot_skip_steps(self):
        services.set_driver(self.delivery, self.driver)
        with self.assertRaises(services.DeliveryError):
            services.advance(self.delivery.pk, self.driver, 'pickup')

    def test_other_driver_cannot_touch_delivery(self):
        services.set_driver(self.delivery, self.driver)
        other = make_driver('driver2')
        with self.assertRaises(Delivery.DoesNotExist):
            services.advance(self.delivery.pk, other, 'accept')

    def test_failed_needs_reason_and_can_be_reassigned(self):
        services.set_driver(self.delivery, self.driver)
        for action in ('accept', 'pickup', 'depart'):
            services.advance(self.delivery.pk, self.driver, action)
        with self.assertRaises(services.DeliveryError):
            services.advance(self.delivery.pk, self.driver, 'fail', reason='')
        services.advance(self.delivery.pk, self.driver, 'fail', reason=Delivery.FAIL_WRONG_ADDRESS)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, Delivery.FAILED)

        other = make_driver('driver2')
        services.set_driver(self.delivery, other)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, Delivery.ASSIGNED)
        self.assertEqual(self.delivery.driver, other)
        self.assertEqual(self.delivery.failure_reason, '')

    def test_cannot_reassign_after_pickup(self):
        services.set_driver(self.delivery, self.driver)
        services.advance(self.delivery.pk, self.driver, 'accept')
        services.advance(self.delivery.pk, self.driver, 'pickup')
        with self.assertRaises(services.DeliveryError):
            services.set_driver(self.delivery, make_driver('driver2'))

    def test_driver_status_busy_and_back(self):
        services.set_driver(self.delivery, self.driver)
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.current_status, Driver.STATUS_BUSY)
        services.cancel(self.delivery)
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.current_status, Driver.STATUS_ONLINE)


class DeliveryViewTests(TestCase):
    def setUp(self):
        self.driver = make_driver(is_online=True)
        self.delivery = make_order().delivery
        services.set_driver(self.delivery, self.driver)

    def test_login_required(self):
        resp = self.client.get(reverse('delivery:dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('delivery:login'), resp['Location'])

    def test_customer_cannot_log_in_to_delivery(self):
        User.objects.create_user('cust', password='pass12345!')
        resp = self.client.post(reverse('delivery:login'), {'username': 'cust', 'password': 'pass12345!'})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_driver_flow_over_http(self):
        self.client.post(reverse('delivery:login'), {'username': 'driver1', 'password': 'pass12345!'})
        self.assertEqual(self.client.get(reverse('delivery:dashboard')).status_code, 200)
        url = reverse('delivery:detail', args=[self.delivery.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(reverse('delivery:action', args=[self.delivery.pk, 'accept']))
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, Delivery.ACCEPTED)

    def test_other_drivers_delivery_is_404(self):
        make_driver('driver2')
        self.client.post(reverse('delivery:login'), {'username': 'driver2', 'password': 'pass12345!'})
        resp = self.client.get(reverse('delivery:detail', args=[self.delivery.pk]))
        self.assertEqual(resp.status_code, 404)
