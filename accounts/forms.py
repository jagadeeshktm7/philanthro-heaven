from django.contrib.auth.forms import UserCreationForm
from django import forms
from .models import CustomUser

class RegisterForm(UserCreationForm):
    # Role choices for registration dropdown
    ROLE_CHOICES = (
        ('donor', 'Donor'),
        ('ngo', 'NGO'),
        ('beneficiary', 'Beneficiary'),
    )

    role = forms.ChoiceField(choices=ROLE_CHOICES, label='Role')
    phone = forms.CharField(required=False, max_length=20, label='Phone Number')
    city = forms.CharField(required=False, max_length=100, label='City')

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'role', 'phone', 'city')

    def save(self, commit=True):
        # Save user and add additional fields
        user = super().save(commit=False)
        user.role = self.cleaned_data.get('role')
        user.phone = self.cleaned_data.get('phone')
        user.city = self.cleaned_data.get('city')
        if commit:
            user.save()
        return user
