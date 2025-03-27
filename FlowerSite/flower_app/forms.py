from django import forms
from django.contrib.auth.models import User

from .models import Order, CustomUser, CartItem
from allauth.account.forms import SignupForm, LoginForm
from django.core.exceptions import ValidationError
import re

class CartAddProductForm(forms.ModelForm):
    class Meta:
        model = CartItem
        fields = ['quantity']
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '99'
            })
        }

class CustomLoginForm(LoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Стилизация полей
        self.fields['login'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Ваш email'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Пароль'
        })

class CustomSignupForm(SignupForm):
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Имя'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Фамилия'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Email'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Пароль'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Пароль (ещё раз)'
        })

class UserEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser  # Используем кастомную модель
        fields = ('first_name', 'last_name', 'email', 'phone')

def validate_phone(value):
    pattern = r'^\+7 \(\d{3}\) \d{3}-\d{2}-\d{2}$'
    if not re.match(pattern, value):
        raise ValidationError('Формат телефона: +7 (999) 123-45-67')

# class CustomSignupForm(SignupForm):
#     first_name = forms.CharField(max_length=30, label="Имя")
#     last_name = forms.CharField(max_length=30, label="Фамилия")
#
#     def save(self, request):
#         user = super().save(request)
#         user.first_name = self.cleaned_data["first_name"]
#         user.last_name = self.cleaned_data["last_name"]
#         user.save()
#         return user
#
#     def clean_password(self):
#         password = self.cleaned_data.get('password1')
#         if len(password) < 10:
#             raise ValidationError('Пароль должен содержать минимум 10 символов')
#         if not any(char.isdigit() for char in password):
#             raise ValidationError('Пароль должен содержать цифры')
#         return password

# class CustomSignupForm(SignupForm):
#     first_name = forms.CharField(
#         max_length=30,
#         label='Имя',
#         widget=forms.TextInput(attrs={'placeholder': 'Иван'}))
#
#     last_name = forms.CharField(
#         max_length=30,
#         label='Фамилия',
#         widget=forms.TextInput(attrs={'placeholder': 'Иванов'}))
#
#     phone = forms.CharField(
#         max_length=20,
#         label='Телефон',
#         widget=forms.TextInput(attrs={'placeholder': '+7 (999) 123-45-67'}))
#
#     consent_marketing = forms.BooleanField(
#         required=False,
#         label='Получать специальные предложения')

def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone = self.cleaned_data['phone']
        user.consent_marketing = self.cleaned_data['consent_marketing']
        user.save()
        return user

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['customer_name', 'phone', 'address', 'products']
        widgets = {
            'products': forms.CheckboxSelectMultiple
        }

# class CustomSignupForm(SignupForm):
#     first_name = forms.CharField(max_length=30, label='Имя')
#     last_name = forms.CharField(max_length=30, label='Фамилия')
#
# def save(self, request):
#     user = super().save(request)
#     user.first_name = self.cleaned_data['first_name']
#     user.last_name = self.cleaned_data['last_name']
#     user.save()
#     return user
#
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # Инициализируем поле телефона из профиля
#         if hasattr(self.instance, 'profile'):
#             self.fields['phone'].initial = self.instance.profile.phone