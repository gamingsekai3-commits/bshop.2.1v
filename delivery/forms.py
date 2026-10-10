from django import forms

from .models import Delivery


class FailDeliveryForm(forms.Form):
    reason = forms.ChoiceField(choices=Delivery.FAILURE_CHOICES, label='Шалтгаан')
    note = forms.CharField(label='Тайлбар', required=False, max_length=500,
                           widget=forms.Textarea(attrs={'rows': 3}))
