from django import forms
from django.contrib.auth import authenticate
from .models import CustomUser


class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-input', 'placeholder': 'Create a secure password'
    }))
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-input', 'placeholder': 'Confirm your password'
    }))

    class Meta:
        model = CustomUser
        fields = ['email', 'full_name', 'phone_number', 'grade', 'curriculum', 'is_student', 'is_tutor']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'student@example.com'}),
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full Name'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'WhatsApp Phone Number (e.g. +27 74 123 4567)'}),
            'grade': forms.Select(attrs={'class': 'form-input'}),
            'curriculum': forms.Select(attrs={'class': 'form-input'}),
            'is_student': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_tutor': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', 'Passwords do not match.')

        # Ensure at least one role is selected
        is_student = cleaned_data.get('is_student')
        is_tutor = cleaned_data.get('is_tutor')
        if not is_student and not is_tutor:
            # Default to student if neither was checked
            cleaned_data['is_student'] = True

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Enter your registered email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Enter password'})
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')

        if email and password:
            email = email.strip().lower()
            self.user_cache = authenticate(self.request, username=email, password=password)
            if self.user_cache is None:
                # Also try email= parameter in case of backend differences
                self.user_cache = authenticate(self.request, email=email, password=password)

            if self.user_cache is None:
                raise forms.ValidationError('Invalid email or password. Please try again.')
            elif not self.user_cache.is_active:
                raise forms.ValidationError('This account has been deactivated.')
        return self.cleaned_data

    def get_user(self):
        return self.user_cache
