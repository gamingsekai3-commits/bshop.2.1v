from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django import forms
from .models import Product, Category, Customer, Employee
from .translations import TRANSLATIONS, DEFAULT_LANGUAGE, active_language, lazy_position, lazy_t

# Ажилтны албан тушаалын сонголтууд (dropdown). Утга нь Employee.position-д текстээр хадгалагдана.
# Label is translated when the page is drawn (Admin / Админ, Operator / Оператор, Хүргэгч / Driver).
POSITION_CHOICES = [
    ('', '— Албан тушаал сонгох —'),
    ('Admin', lazy_position('Admin')),
    ('Хүргэгч', lazy_position('Хүргэгч')),
    ('Operator', lazy_position('Operator')),
]


def position_choices_with(current=''):
    """Хуучин (жагсаалтад байхгүй) утгатай ажилтныг засахад утга нь алдагдахгүйн тулд түр нэмнэ."""
    choices = list(POSITION_CHOICES[1:])
    if current and current not in [c[0] for c in choices]:
        choices.append((current, lazy_position(current)))
    return choices


class RegisterForm(UserCreationForm):
    email = forms.EmailField(label="", required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(label="", max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label="", max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def __init__(self, *args, lang=DEFAULT_LANGUAGE, **kwargs):
        super(RegisterForm, self).__init__(*args, **kwargs)
        t = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE])

        self.fields['email'].widget.attrs['placeholder'] = t['email_placeholder']
        self.fields['first_name'].widget.attrs['placeholder'] = t['first_name_placeholder']
        self.fields['last_name'].widget.attrs['placeholder'] = t['last_name_placeholder']

        self.fields['username'].widget.attrs['class'] = 'form-control'
        self.fields['username'].widget.attrs['placeholder'] = t['username_placeholder']
        self.fields['username'].label = ''
        self.fields['username'].help_text = f'<span class="form-text text-muted"><small>{t["username_help_text"]}</small></span>'

        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password1'].widget.attrs['placeholder'] = t['password_placeholder']
        self.fields['password1'].label = ''
        self.fields['password1'].help_text = f'<span class="form-text text-muted"><small>{t["password_help_text"]}</small></span>'

        self.fields['password2'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['placeholder'] = t['password_confirm_placeholder']
        self.fields['password2'].label = ''
        self.fields['password2'].help_text = f'<span class="form-text text-muted"><small>{t["password_confirm_help_text"]}</small></span>'


class EmployeeForm(UserCreationForm):
    email = forms.EmailField(label="", required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(label="", max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(label="", max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    position = forms.ChoiceField(label="", choices=POSITION_CHOICES, required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    phone = forms.CharField(label="", max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def __init__(self, *args, lang=DEFAULT_LANGUAGE, **kwargs):
        super(EmployeeForm, self).__init__(*args, **kwargs)
        t = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE])

        self.fields['email'].widget.attrs['placeholder'] = t['email_placeholder']
        self.fields['first_name'].widget.attrs['placeholder'] = t['first_name_placeholder']
        self.fields['last_name'].widget.attrs['placeholder'] = t['last_name_placeholder']
        self.fields['phone'].widget.attrs['placeholder'] = t['phone_placeholder']

        self.fields['username'].widget.attrs['class'] = 'form-control'
        self.fields['username'].widget.attrs['placeholder'] = t['username_placeholder']
        self.fields['username'].label = ''
        self.fields['username'].help_text = f'<span class="form-text text-muted"><small>{t["username_help_text"]}</small></span>'

        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password1'].widget.attrs['placeholder'] = t['password_placeholder']
        self.fields['password1'].label = ''
        self.fields['password1'].help_text = f'<span class="form-text text-muted"><small>{t["password_help_text"]}</small></span>'

        self.fields['password2'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['placeholder'] = t['password_confirm_placeholder']
        self.fields['password2'].label = ''
        self.fields['password2'].help_text = f'<span class="form-text text-muted"><small>{t["password_confirm_help_text"]}</small></span>'

    def save(self, commit=True):
        user = super().save(commit=False)
        # This is what makes the account an "employee": is_staff grants
        # access to /admin/ but not the full superuser privileges. The
        # post_save signal on User (see store/models.py) sees is_staff is
        # already True and creates the matching Employee row automatically.
        user.is_staff = True
        if commit:
            user.save()
            employee = user.employee_profile
            employee.position = self.cleaned_data.get('position', '') or employee.position
            employee.phone = self.cleaned_data.get('phone', '')
            employee.save()
        return user


class CustomerProfileForm(forms.ModelForm):
    """Lets a logged-in customer edit their own private info: phone number
    and home address/location. Nothing here is visible to other customers."""
    class Meta:
        model = Customer
        fields = ['phone', 'address']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, lang=DEFAULT_LANGUAGE, **kwargs):
        super().__init__(*args, **kwargs)
        t = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE])
        self.fields['phone'].label = t['phone_placeholder']
        self.fields['address'].label = t['customer_address_label']
        self.fields['address'].widget.attrs['placeholder'] = t['customer_address_placeholder']


class EmployeeProfileForm(forms.ModelForm):
    """Lets a logged-in employee edit their own phone number and position."""
    position = forms.ChoiceField(choices=POSITION_CHOICES[1:], widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = Employee
        fields = ['phone', 'position']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, lang=DEFAULT_LANGUAGE, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['position'].choices = position_choices_with(getattr(self.instance, 'position', ''))
        t = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE])
        self.fields['phone'].label = t['phone_placeholder']
        self.fields['position'].label = t['table_position']


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'price', 'cost_price', 'category', 'description', 'image', 'is_sale', 'sale_price', 'stock', 'rating']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0', 'min': '0'}),
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.0', 'min': '0', 'max': '5', 'step': '0.1'}),
        }

    def __init__(self, *args, lang=None, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        # The Django admin builds this form without a `lang`, so fall back to
        # the language the middleware switched on for this request.
        t = TRANSLATIONS[lang] if lang in TRANSLATIONS else TRANSLATIONS[active_language()]

        self.fields['name'].label = t['form_name_label']
        self.fields['name'].widget.attrs['placeholder'] = t['form_name_label']
        self.fields['price'].label = t['form_price_label']
        self.fields['cost_price'].label = t['admin_cost_price']
        self.fields['category'].label = t['form_category_label']
        self.fields['description'].label = t['form_description_label']
        self.fields['description'].widget.attrs['placeholder'] = t['form_description_label'] + '...'
        self.fields['image'].label = t['form_image_label']
        self.fields['is_sale'].label = t['sale_checkbox_label']
        self.fields['sale_price'].label = t['sale_price_label']
        self.fields['stock'].label = t['form_stock_label']
        self.fields['rating'].label = t['form_rating_label']

    def clean_image(self):
        image = self.cleaned_data.get('image')

        if not image and not self.instance.image:
            raise forms.ValidationError(lazy_t('err_product_image_required'))

        return image