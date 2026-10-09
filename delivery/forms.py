from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Delivery, Driver


class DriverLoginForm(AuthenticationForm):
    """Ердийн нэвтрэлт + зөвхөн идэвхтэй хүргэгч нэвтэрч чадна."""

    username = forms.CharField(label='Нэвтрэх нэр', widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'}))
    password = forms.CharField(label='Нууц үг', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'Нэвтрэх нэр эсвэл нууц үг буруу байна.',
        'inactive': 'Энэ бүртгэл идэвхгүй байна.',
        'not_driver': 'Энэ бүртгэл хүргэгчийн эрхгүй байна.',
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not Driver.objects.filter(user=user, is_active=True).exists():
            raise forms.ValidationError(self.error_messages['not_driver'], code='not_driver')


class FailDeliveryForm(forms.Form):
    reason = forms.ChoiceField(choices=Delivery.FAILURE_CHOICES, label='Шалтгаан')
    note = forms.CharField(label='Тайлбар', required=False, max_length=500,
                           widget=forms.Textarea(attrs={'rows': 3}))
