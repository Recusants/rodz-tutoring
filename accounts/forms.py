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
    profile_picture = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
        help_text="Required for tutor applicants. Upload a clear portrait headshot."
    )
    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Tell us about your teaching experience and subjects you tutor...'}),
        help_text="Provide details of your teaching qualifications or subjects taught."
    )

    class Meta:
        model = CustomUser
        fields = ['email', 'full_name', 'phone_number', 'grade', 'curriculum', 'is_student', 'is_tutor', 'profile_picture', 'bio']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'student@example.com'}),
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full Name'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'WhatsApp Phone Number (e.g. +27 74 123 4567)'}),
            'grade': forms.Select(attrs={'class': 'form-input'}),
            'curriculum': forms.Select(attrs={'class': 'form-input'}),
            'is_student': forms.CheckboxInput(attrs={'class': 'form-checkbox', 'id': 'id_is_student'}),
            'is_tutor': forms.CheckboxInput(attrs={'class': 'form-checkbox', 'id': 'id_is_tutor'}),
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
            cleaned_data['is_student'] = True

        # If applying for tutor, validate photo and contact details
        if is_tutor:
            email = cleaned_data.get('email')
            phone = cleaned_data.get('phone_number')
            pic = cleaned_data.get('profile_picture')
            if not email:
                self.add_error('email', 'Email address is required for tutor application.')
            if not phone:
                self.add_error('phone_number', 'A WhatsApp / phone number is required for tutor verification.')
            if not pic:
                self.add_error('profile_picture', 'Please upload a profile photo for admin verification.')

        return cleaned_data

    def save(self, commit=True):
        from django.utils import timezone
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])

        is_tutor_applied = self.cleaned_data.get('is_tutor')
        if is_tutor_applied:
            # Tutors require admin manual review before is_tutor is enabled
            user.is_tutor = False
            user.tutor_status = 'PENDING'
            user.tutor_applied_at = timezone.now()
            user.is_student = True
        else:
            user.tutor_status = 'NONE'

        if commit:
            user.save()
        return user


class TutorApplicationForm(forms.ModelForm):
    profile_picture = forms.ImageField(
        required=True,
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
        help_text="Upload a clear headshot photo for your tutor profile."
    )
    phone_number = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. +27 74 123 4567'}),
        help_text="Active WhatsApp phone number for student & admin communications."
    )
    bio = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Detail your teaching credentials, subject expertise, and curriculum background...'}),
        help_text="Explain which subjects and grades you can teach."
    )

    class Meta:
        model = CustomUser
        fields = ['profile_picture', 'phone_number', 'bio']


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
    tutor_status = forms.ChoiceField(
        choices=CustomUser.TUTOR_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-input'})
    )

    class Meta:
        model = CustomUser
        fields = [
            'email', 'full_name', 'phone_number', 'grade', 'curriculum',
            'is_student', 'is_tutor', 'tutor_status', 'is_admin_role', 'is_staff', 'is_active',
            'profile_picture', 'bio'
        ]
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'full_name': forms.TextInput(attrs={'class': 'form-input'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'grade': forms.Select(attrs={'class': 'form-input'}),
            'curriculum': forms.Select(attrs={'class': 'form-input'}),
            'tutor_status': forms.Select(attrs={'class': 'form-input'}),
            'is_student': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_tutor': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_admin_role': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'bio': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
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
