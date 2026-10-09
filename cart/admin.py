from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Case, CharField, DecimalField, ExpressionWrapper, F, Sum, Value, When
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join

from delivery import services as delivery_services
from delivery.models import Delivery, Driver
from store.admin import LIST, ActiveStatusAdmin, _lab_active
from store.translations import get_translations, lazy_t

from .models import Order, OrderItem

# --------------------------------------------------------------------------
# "Төлөв" - the 5 states the admin sees in the order list
# --------------------------------------------------------------------------
# They are NOT a new database column: they are worked out from the order's
# own status plus its delivery's status, so dashboards / reports that count
# pending / confirmed / delivered keep working exactly as before.
#
#   Шинэ захиалгууд    order pending (nobody holds it yet)
#   Бэлтгэгдэж буй     driver assigned, goods not yet on the road
#                      (delivery: assigned / accepted / picked_up / failed)
#   Хүргэлтэнд гарсан  delivery on the way (or an old confirmed order with no delivery row)
#   Хүргэгдсэн         order delivered
#   Цуцлагдсан         order cancelled
ST_NEW, ST_PREPARING, ST_ON_THE_WAY, ST_DELIVERED, ST_CANCELLED = (
    'new', 'preparing', 'on_the_way', 'delivered', 'cancelled')

ORDER_STATE_KEYS = {
    ST_NEW: 'ord_st_new',
    ST_PREPARING: 'ord_st_preparing',
    ST_ON_THE_WAY: 'ord_st_on_the_way',
    ST_DELIVERED: 'ord_st_delivered',
    ST_CANCELLED: 'ord_st_cancelled',
}
ORDER_STATE_COLORS = {
    ST_NEW: '#2980b9',
    ST_PREPARING: '#d35400',
    ST_ON_THE_WAY: '#8e44ad',
    ST_DELIVERED: '#27ae60',
    ST_CANCELLED: '#95a5a6',
}


def order_state_expr():
    return Case(
        When(status=Order.STATUS_CANCELLED, then=Value(ST_CANCELLED)),
        When(status=Order.STATUS_DELIVERED, then=Value(ST_DELIVERED)),
        When(status=Order.STATUS_PENDING, then=Value(ST_NEW)),
        When(delivery__status__in=[Delivery.ASSIGNED, Delivery.ACCEPTED,
                                   Delivery.PICKED_UP, Delivery.FAILED],
             then=Value(ST_PREPARING)),
        default=Value(ST_ON_THE_WAY),
        output_field=CharField(),
    )


def _lab_order_state(raw, T, en):
    return T[ORDER_STATE_KEYS.get(raw, 'ord_st_new')]


def available_drivers():
    """Drivers the admin may hand a NEW order to: active and not offline."""
    return (Driver.objects.filter(is_active=True)
            .exclude(current_status=Driver.STATUS_OFFLINE)
            .select_related('user').order_by('user__username'))


class OrderStateFilter(admin.SimpleListFilter):
    """Sidebar filter with the same 5 states as the Төлөв column."""
    title = lazy_t('admin_status')
    parameter_name = 'state'

    def lookups(self, request, model_admin):
        T = get_translations(request)
        return [(k, T[key]) for k, key in ORDER_STATE_KEYS.items()]

    def queryset(self, request, queryset):
        if self.value() in ORDER_STATE_KEYS:
            return queryset.filter(display_status=self.value())
        return queryset


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'name', 'options', 'price', 'quantity')
    can_delete = False


@admin.register(Order)
class OrderAdmin(ActiveStatusAdmin):
    # Төлөв  - plain text (no dropdown): see order_state_expr() above.
    # Хүргэгч - a dropdown ONLY while the order is new; choosing a driver
    #           moves it to "Бэлтгэгдэж буй" and the cell becomes the driver's name.
    # Идэвхтэй эсэх - one column (it used to be shown twice, as a badge and as a checkbox).
    list_display = ('id', 'name', 'phone', 'status_text', 'driver_cell', 'created_at',
                    'get_total_price', 'is_active')
    list_editable = ('is_active',)
    list_filter = (OrderStateFilter, 'is_active', 'created_at')
    list_select_related = ('delivery__driver__user',)
    search_fields = ('name', 'phone', 'address', 'user__username', 'delivery__driver__user__username')
    readonly_fields = ('picked_at', 'delivered_at')
    # The old Order.courier field is no longer shown anywhere in the admin.
    exclude = ('courier',)
    inlines = [OrderItemInline]
    actions = ['make_active', 'make_inactive']
    column_filters = {
        'status_text': (LIST, 'display_status', _lab_order_state),
        'is_active': (LIST, 'is_active', _lab_active),
    }

    class Media:
        js = ('admin/js/assign-driver.js',)

    def get_queryset(self, request):
        # display_status first (plain annotation), then the Total column's sum, so the
        # Total column can still be sorted (it is a sum over the order's items).
        return (super().get_queryset(request)
                .annotate(display_status=order_state_expr())
                .annotate(total_sort=Sum(ExpressionWrapper(
                    F('items__price') * F('items__quantity'),
                    output_field=DecimalField(max_digits=14, decimal_places=2)))))

    # -- columns ----------------------------------------------------------

    @admin.display(description=lazy_t('admin_total'), ordering='total_sort')
    def get_total_price(self, obj):
        return obj.get_total_price()

    @admin.display(description=lazy_t('admin_status'))
    def status_text(self, obj):
        key = ORDER_STATE_KEYS.get(obj.display_status, 'ord_st_new')
        return format_html('<b style="color:{}">{}</b>',
                           ORDER_STATE_COLORS.get(obj.display_status, '#000'), str(lazy_t(key)))

    def prepare_rows(self, request, rows):
        """Called once per page by BshopChangeList: load the dropdown options one time."""
        drivers = [(d.pk, d.display_name) for d in available_drivers()]
        for row in rows:
            row._driver_options = drivers

    @admin.display(description=lazy_t('dl_f_driver'))
    def driver_cell(self, obj):
        # Not new any more -> the driver's name as text.
        if obj.display_status != ST_NEW:
            delivery = getattr(obj, 'delivery', None)      # missing row -> None
            driver = delivery.driver if delivery else None
            return driver.display_name if driver else '-'
        if not obj.is_active:
            return '-'
        # New order -> dropdown with the drivers that are not offline.
        options = getattr(obj, '_driver_options', None)
        if options is None:                                  # rendered outside the changelist
            options = [(d.pk, d.display_name) for d in available_drivers()]
        if not options:
            return format_html('<span style="color:#95a5a6">{}</span>', str(lazy_t('ord_no_driver_online')))
        return format_html(
            '<select class="js-assign-driver" data-url="{}" style="min-width:150px">'
            '<option value="">{}</option>{}</select>',
            reverse('admin:cart_order_assign_driver', args=[obj.pk]),
            str(lazy_t('ord_pick_driver')),
            format_html_join('', '<option value="{}">{}</option>', options),
        )

    # -- assigning a driver from the list ---------------------------------

    def get_urls(self):
        custom = [
            path('<int:order_id>/assign-driver/',
                 self.admin_site.admin_view(self.assign_driver_view),
                 name='cart_order_assign_driver'),
        ]
        return custom + super().get_urls()      # ours first: the stock "<path:object_id>/" would swallow it

    def assign_driver_view(self, request, order_id):
        if request.method != 'POST':
            return HttpResponseNotAllowed(['POST'])
        if not self.has_change_permission(request):
            raise PermissionDenied
        T = get_translations(request)
        order = get_object_or_404(Order, pk=order_id, is_active=True)
        if order.status != Order.STATUS_PENDING:
            return JsonResponse({'ok': False, 'error': T['ord_assign_not_new']}, status=400)
        driver = available_drivers().filter(pk=request.POST.get('driver') or 0).first()
        if driver is None:
            return JsonResponse({'ok': False, 'error': T['ord_assign_bad_driver']}, status=400)
        try:
            delivery = delivery_services.create_delivery_for_order(order)
            # Sets the driver, Delivery -> assigned, Order -> confirmed (= "Бэлтгэгдэж буй") and logs it.
            delivery_services.set_driver(delivery, driver, by=request.user)
        except delivery_services.DeliveryError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True})
