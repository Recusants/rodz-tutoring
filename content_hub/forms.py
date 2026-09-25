from django import forms
from .models import Course, ContentItem, Subject, Curriculum


COVER_CHOICES = [
    ('caps-g12-maths.svg', 'Mathematics (CAPS / IEB)'),
    ('caps-g12-physics.svg', 'Physical Sciences / Physics'),
    ('cambridge-puremaths.svg', 'Cambridge AS/A Level Maths'),
    ('caps-g11-chem.svg', 'Chemistry / Science Lab'),
    ('caps-g10-accounting.svg', 'Accounting & Commercial Studies'),
    ('caps-g12-life-sciences.svg', 'Life Sciences / Biology'),
    ('caps-pastpapers.svg', 'Past Examination Papers & Memos'),
]


class TutorCourseCreateForm(forms.ModelForm):
    cover_svg_name = forms.ChoiceField(
        choices=COVER_CHOICES,
        initial='caps-g12-maths.svg',
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    items = forms.ModelMultipleChoiceField(
        queryset=ContentItem.objects.all().order_by('subject__name', 'grade', 'title'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'item-checkbox'}),
        required=True,
        help_text="Select all video lessons, study packs, and worksheets to include in this course bundle."
    )

    class Meta:
        model = Course
        fields = [
            'title',
            'subject',
            'grade',
            'curriculum',
            'bundle_price',
            'cover_svg_name',
            'description',
            'items',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Master Grade 12 Calculus & Trigonometry'}),
            'subject': forms.Select(attrs={'class': 'form-input'}),
            'grade': forms.Select(attrs={'class': 'form-input'}),
            'curriculum': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. CAPS & IEB'}),
            'bundle_price': forms.NumberInput(attrs={'class': 'form-input', 'min': 10, 'placeholder': '120'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Provide a detailed syllabus description for students...'}),
        }
        help_texts = {
            'bundle_price': 'Set the total price in coins for this complete bundle. Students who already bought individual items will have those costs automatically deducted!',
        }

    def clean_bundle_price(self):
        price = self.cleaned_data.get('bundle_price')
        if price is not None and price < 5:
            raise forms.ValidationError("Bundle price must be at least 5 coins.")
        return price
