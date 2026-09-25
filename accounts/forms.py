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


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['full_name', 'phone_number', 'grade', 'curriculum']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full Name'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'WhatsApp Contact Number'}),
            'grade': forms.Select(attrs={'class': 'form-input'}),
            'curriculum': forms.Select(attrs={'class': 'form-input'}),
        }


from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm, SetPasswordForm


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-input'})


class StyledPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Enter your registered email address'
        })


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-input'})


class AdminSystemSettingsForm(forms.Form):
    system_email = forms.EmailField(
        label="System Sender Email",
        help_text="Sender address shown on password reset emails and system alerts",
        widget=forms.EmailInput(attrs={'class': 'form-input'})
    )
    notification_email = forms.EmailField(
        label="Notification Recipient Email",
        help_text="Admin address where new user alerts, inquiries, and orders are sent",
        widget=forms.EmailInput(attrs={'class': 'form-input'})
    )
    email_host = forms.CharField(
        label="SMTP Email Host Server",
        help_text="e.g. smtp.gmail.com, mail.rodztutoring.co.za",
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    email_port = forms.IntegerField(
        label="SMTP Port",
        help_text="e.g. 587 (TLS), 465 (SSL), or 25",
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )
    email_host_user = forms.CharField(
        label="SMTP Account / Username",
        required=False,
        help_text="Your email address or username on the mail server",
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    email_host_password = forms.CharField(
        label="SMTP / App Password",
        required=False,
        help_text="Google App Password (16 characters) or email account password (leave blank to keep existing password)",
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': '••••••••••••••••'})
    )
    email_use_tls = forms.BooleanField(
        label="Use TLS Encryption",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'})
    )
    whatsapp_phone = forms.CharField(
        label="WhatsApp Number (Numeric Format for Links)",
        help_text="e.g. 27745685212 (country code + number without plus or spaces)",
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )
    whatsapp_display_phone = forms.CharField(
        label="WhatsApp Display Format",
        help_text="e.g. +27 74 568 5212 (as shown to learners on the website)",
        widget=forms.TextInput(attrs={'class': 'form-input'})
    )


from content_hub.models import ContentItem


class AdminUserEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = [
            'email', 'full_name', 'phone_number', 'grade', 'curriculum',
            'is_student', 'is_tutor', 'is_admin_role', 'is_staff', 'is_active'
        ]
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'full_name': forms.TextInput(attrs={'class': 'form-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'grade': forms.Select(attrs={'class': 'form-input'}),
            'curriculum': forms.Select(attrs={'class': 'form-input'}),
            'is_student': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_tutor': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_admin_role': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class AdminUserCreateForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Initial password'}),
        help_text="Provide an initial password for the account."
    )
    initial_coins = forms.IntegerField(
        required=False,
        initial=50,
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-input'}),
        help_text="Optional starting coins to credit to this student's wallet."
    )

    class Meta:
        model = CustomUser
        fields = [
            'email', 'full_name', 'phone_number', 'grade', 'curriculum',
            'is_student', 'is_tutor', 'is_admin_role', 'is_staff', 'is_active'
        ]
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'full_name': forms.TextInput(attrs={'class': 'form-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'grade': forms.Select(attrs={'class': 'form-input'}),
            'curriculum': forms.Select(attrs={'class': 'form-input'}),
            'is_student': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_tutor': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_admin_role': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class AdminDirectPasswordResetForm(forms.Form):
    new_password = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Enter new password'}),
        help_text="Minimum 6 characters. Overwrites user password immediately without requiring old password."
    )
    confirm_password = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Repeat new password'})
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password')
        p2 = cleaned.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned


class AdminWalletAdjustForm(forms.Form):
    ACTION_CHOICES = [
        ('CREDIT', 'Credit (Add Coins)'),
        ('DEBIT', 'Debit (Deduct Coins)'),
    ]
    action_type = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    coins = forms.IntegerField(
        min_value=1,
        initial=50,
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )
    description = forms.CharField(
        label="Audit Reason / Note",
        help_text="Explain why coins are being adjusted (visible in audit logs)",
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Scholarship reward, payment correction, manual gift'})
    )


class AdminGrantUnlockForm(forms.Form):
    content_item = forms.ModelChoiceField(
        queryset=ContentItem.objects.all().order_by('grade', 'subject__name', 'title'),
        widget=forms.Select(attrs={'class': 'form-input'})
    )
