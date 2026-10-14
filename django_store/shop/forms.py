from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Order


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=60)
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ["username", "first_name", "email"]

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["full_name", "phone", "address", "city", "pincode", "payment"]
        widgets = {"payment": forms.RadioSelect}

    def clean_phone(self):
        p = self.cleaned_data["phone"].replace(" ", "")
        if not (p.isdigit() and len(p) == 10):
            raise forms.ValidationError("Enter a 10-digit mobile number.")
        return p

    def clean_pincode(self):
        p = self.cleaned_data["pincode"]
        if not (p.isdigit() and len(p) == 6):
            raise forms.ValidationError("Enter a 6-digit PIN code.")
        return p
