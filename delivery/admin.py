from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.urls import reverse
from django.utils.html import format_html

from store.translations import lazy_t
from store.admin import ActiveStatusAdmin, BshopChangeList, PopupFriendlyAdmin

from . import services
from .models import Delivery, DeliveryHistory, Driver

User = get_user_model()

STATUS_COLORS = {
    Delivery.PENDING: '#7f8c8d',
    Delivery.ASSIGNED: '#2980b9',
    Delivery.ACCEPTED: '#8e44ad',
    Delivery.PICKED_UP: '#d35400',
    Delivery.ON_THE_WAY: '#e67e22',
    Delivery.DELIVERED: '#27ae60',
    Delivery.FAILED: '#c0392b',
    Delivery.CANCELLED: '#95a5a6',
}


class DriverAdminForm(forms.ModelForm):
    """Хүргэгч нэмэхэд нэвтрэх нэр / нууц үгийг энэ дороос нь шууд үүсгэнэ."""

    username = forms.CharField(label=lazy_t('dl_col_username'), max_length=150, required=False)
    password = forms.CharField(label=lazy_t('dl_col_password'), widget=forms.PasswordInput(render_value=False), required=False)
    full_name = forms.CharField(label=lazy_t('dl_col_name'), max_length=150, required=False)

    class Meta:
        model = Driver
        fields = '__all__'

    def clean(self):
        data = super().clean()
        if self.instance.pk:
            return data
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        if not username:
            self.add_error('username', lazy_t('dl_err_username_required'))
        elif User.objects.filter(username__iexact=username).exists():
            self.add_error('username', lazy_t('dl_err_username_taken'))
        if not password:
            self.add_error('password', lazy_t('dl_err_password_required'))
        else:
            try:
                validate_password(password)
            except forms.ValidationError as exc:
                self.add_error('password', exc)
        data['username'] = username
        return data


@admin.register(Driver)
class DriverAdmin(ActiveStatusAdmin):
    sortable_by = () 
    form = DriverAdminForm
    list_display = ('id', 'name', 'username', 'phone', 'status_text', 'is_online', 'status_badge', 'is_active')
    list_filter = ('is_active', 'is_online', 'current_status')
    search_fields = ('user__username', 'user__first_name', 'phone')
    list_select_related = ('user',)
    column_filters = {**ActiveStatusAdmin.column_filters}

    def get_fields(self, request, obj=None):
        if obj is None:
            return ('username', 'password', 'full_name', 'phone', 'is_active')
        return ('user', 'phone', 'is_active', 'is_online', 'current_status')

    def get_readonly_fields(self, request, obj=None):
        return ('user', 'current_status') if obj else ()

    @admin.display(description=lazy_t('dl_col_name'), ordering='user__first_name')
    def name(self, obj):
        return obj.display_name

    @admin.display(description=lazy_t('dl_col_username'), ordering='user__username')
    def username(self, obj):
        return obj.user.username

    @admin.display(description=lazy_t('dl_f_work_status'))
    def status_text(self, obj):
        color = {'online': '#27ae60', 'busy': '#e67e22', 'offline': '#95a5a6'}[obj.current_status]
        return format_html('<b style="color:{}">{}</b>', color, obj.get_current_status_display())

    def save_model(self, request, obj, form, change):
        if not change:
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data.get('full_name', ''),
            )
            # store.models-ийн signal энгийн хэрэглэгч бүрт Customer мөр үүсгэдэг.
            # Хүргэгч худалдан авагчдын жагсаалтад орох ёсгүй.
            user.customer_profile.delete()
            obj.user = user
        super().save_model(request, obj, form, change)
        obj.refresh_status()


class DeliveryHistoryInline(admin.TabularInline):
    model = DeliveryHistory
    extra = 0
    can_delete = False
    fields = ('created_at', 'from_status', 'to_status', 'driver', 'changed_by', 'note')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Delivery)
class DeliveryAdmin(PopupFriendlyAdmin, admin.ModelAdmin):
    sortable_by = () 
    list_display = ('id', 'order_link', 'customer', 'short_address', 'district', 'driver', 'status_badge', 'created_at')
    # Жагсаалтад хүргэгч зөвхөн текстээр харагдана (dropdown биш). Хүргэгчийг
    # Захиалга цэсний жагсаалтаас, эсвэл мөрийг нээгээд засах цонхоос онооно.
    list_display_links = ('id',)
    list_filter = ('status', 'driver', 'created_at', 'district')
    search_fields = ('order__id', 'order__name', 'phone', 'delivery_address', 'driver__user__username')
    list_select_related = ('order', 'driver', 'driver__user')
    list_per_page = 10
    inlines = [DeliveryHistoryInline]
    actions = ['cancel_deliveries']

    fields = ('order', 'driver', 'status', 'delivery_address', 'district', 'phone', 'note',
              'failure_reason', 'created_at', 'assigned_at', 'accepted_at', 'picked_up_at',
              'on_the_way_at', 'unloaded_at', 'delivered_at', 'failed_at')
    # Төлөв хүргэгчийн app-аар (эсвэл хүргэгч оноох үед) л өөрчлөгдөнө.
    readonly_fields = ('order', 'status', 'failure_reason', 'created_at', 'assigned_at', 'accepted_at',
                       'picked_up_at', 'on_the_way_at', 'unloaded_at', 'delivered_at', 'failed_at')

    def get_changelist(self, request, **kwargs):
        return BshopChangeList

    def has_add_permission(self, request):
        # Хүргэлт захиалгаас автоматаар үүснэ.
        return False

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        # Хүргэгч сонгох dropdown-ы хажууд Django-гийн засах / нэмэх / устгах / харах
        # дүрс гардаг. Эндээс хүргэгч үүсгэх, засах шаардлагагүй тул бүгдийг нь хаана.
        if db_field.name == 'driver':
            for flag in ('can_add_related', 'can_change_related', 'can_delete_related', 'can_view_related'):
                if hasattr(field.widget, flag):
                    setattr(field.widget, flag, False)
        return field

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'driver' in form.base_fields:
            form.base_fields['driver'].queryset = Driver.objects.filter(is_active=True).select_related('user')
        return form

    @admin.display(description=lazy_t('dl_f_order'), ordering='order_id')
    def order_link(self, obj):
        url = reverse('admin:cart_order_change', args=[obj.order_id])
        return format_html('<a href="{}">#{}</a>', url, obj.order_id)

    @admin.display(description=lazy_t('dl_col_customer'), ordering='order__name')
    def customer(self, obj):
        return obj.order.name

    @admin.display(description=lazy_t('dl_col_address'))
    def short_address(self, obj):
        text = obj.delivery_address or ''
        return text if len(text) <= 40 else text[:40] + '…'

    @admin.display(description=lazy_t('dl_f_status'), ordering='status')
    def status_badge(self, obj):
        return format_html('<b style="color:{}">&#9679; {}</b>',
                           STATUS_COLORS.get(obj.status, '#000'), obj.get_status_display())

    def save_model(self, request, obj, form, change):
        new_driver = obj.driver
        if change:
            old = Delivery.objects.get(pk=obj.pk)
            # Хүргэгчийг өөрөө шууд бичихгүй: services.set_driver төлөв, түүхийг зөв тохируулна.
            obj.driver_id = old.driver_id
            obj.status = old.status
        super().save_model(request, obj, form, change)
        if new_driver != obj.driver:
            try:
                services.set_driver(obj, new_driver, by=request.user)
            except services.DeliveryError as exc:
                self.message_user(request, f"{lazy_t('dl_f_delivery')} #{obj.pk}: {exc}", level=messages.ERROR)

    @admin.action(description=lazy_t('dl_action_cancel'))
    def cancel_deliveries(self, request, queryset):
        done = 0
        for delivery in queryset.select_related('driver', 'driver__user'):
            try:
                services.cancel(delivery, by=request.user)
                done += 1
            except services.DeliveryError as exc:
                self.message_user(request, f"{lazy_t('dl_f_delivery')} #{delivery.pk}: {exc}", level=messages.WARNING)
        self.message_user(request, f"{done} {lazy_t('dl_msg_cancelled')}")


@admin.register(DeliveryHistory)
class DeliveryHistoryAdmin(admin.ModelAdmin):
    sortable_by = () 
    list_display = ('created_at', 'delivery', 'from_status', 'to_status', 'driver', 'changed_by', 'note')
    list_filter = ('to_status', 'driver', 'created_at')
    search_fields = ('delivery__id', 'delivery__order__id', 'note')
    list_select_related = ('delivery', 'driver', 'driver__user', 'changed_by')
    list_per_page = 25

    def get_changelist(self, request, **kwargs):
        return BshopChangeList

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False