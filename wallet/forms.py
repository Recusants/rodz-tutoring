from django import forms
from .models import CoinBundle, PaymentMethod, CoinPaymentRequest


class CoinPaymentActivationForm(forms.ModelForm):
    bundle = forms.ModelChoiceField(
        queryset=CoinBundle.objects.filter(is_active=True).order_by('order', 'price_zar'),
        empty_label="-- Select Coin Bundle --",
        widget=forms.Select(attrs={'class': 'input-control', 'id': 'id_bundle'}),
        help_text="Select the bundle you paid for"
    )
    payment_method = forms.ModelChoiceField(
        queryset=PaymentMethod.objects.filter(is_active=True).order_by('order'),
        empty_label="-- Select Payment Method Used --",
        widget=forms.Select(attrs={'class': 'input-control', 'id': 'id_payment_method'}),
        help_text="Select the banking/payment method you used to transfer funds"
    )
    reference_number = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={
            'class': 'input-control', 
            'placeholder': 'e.g. Bank Ref, EFT Transaction ID, or Deposit Name',
            'id': 'id_reference_number'
        }),
        help_text="The reference or receipt ID shown on your bank confirmation"
    )
    proof_of_payment = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'input-control',
            'accept': 'image/*,.pdf',
            'id': 'id_proof_of_payment'
        }),
        help_text="Accepted formats: PDF or images (PNG, JPG, JPEG) up to 10MB"
    )
    student_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'input-control', 
            'rows': 2, 
            'placeholder': 'Optional: Add any notes for the admin verifier'
        })
    )

    class Meta:
        model = CoinPaymentRequest
        fields = ['bundle', 'payment_method', 'reference_number', 'proof_of_payment', 'student_notes']

    def clean_proof_of_payment(self):
        file = self.cleaned_data.get('proof_of_payment')
        if file:
            # 10MB limit
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError("Proof of payment file size must not exceed 10MB.")
        return file
