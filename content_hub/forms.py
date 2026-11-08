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


class ContentItemUploadForm(forms.ModelForm):
    cover_svg_name = forms.ChoiceField(
        choices=COVER_CHOICES,
        initial='caps-g12-maths.svg',
        widget=forms.Select(attrs={'class': 'form-input'}),
        help_text="Visual cover style for catalog cards"
    )

    class Meta:
        model = ContentItem
        fields = [
            'title',
            'subject',
            'grade',
            'curriculum',
            'content_type',
            'category',
            'is_free',
            'allow_download',
            'coin_price',
            'pdf_file',
            'video_file',
            'youtube_url',
            'cover_svg_name',
            'description',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Grade 12 Calculus Past Paper 1 Solutions'}),
            'subject': forms.Select(attrs={'class': 'form-input'}),
            'grade': forms.Select(attrs={'class': 'form-input'}),
            'curriculum': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. CAPS & IEB'}),
            'content_type': forms.Select(attrs={'class': 'form-input'}),
            'category': forms.Select(attrs={'class': 'form-input'}),
            'is_free': forms.CheckboxInput(attrs={'class': 'form-checkbox', 'id': 'id_is_free'}),
            'allow_download': forms.CheckboxInput(attrs={'class': 'form-checkbox', 'id': 'id_allow_download'}),
            'coin_price': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'placeholder': '50'}),
            'pdf_file': forms.FileInput(attrs={'class': 'form-input', 'accept': '.pdf'}),
            'video_file': forms.FileInput(attrs={'class': 'form-input', 'accept': 'video/mp4,video/webm'}),
            'youtube_url': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://youtube.com/watch?v=... or Vimeo URL'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Detailed syllabus summary and study guidelines...'}),
        }
        help_texts = {
            'is_free': 'If checked, all learners can view this material without spending coins.',
            'allow_download': 'Allow learners to download this file directly (Only applies to free resources).',
            'coin_price': 'Coins required to unlock if not free (ignored when free is checked).',
        }

    def clean(self):
        cleaned_data = super().clean()
        is_free = cleaned_data.get('is_free')
        allow_download = cleaned_data.get('allow_download')
        content_type = cleaned_data.get('content_type')
        pdf_file = cleaned_data.get('pdf_file')
        video_file = cleaned_data.get('video_file')
        youtube_url = cleaned_data.get('youtube_url')

        if not is_free and allow_download:
            # Enforce that only free items can be downloadable
            cleaned_data['allow_download'] = False

        if content_type == 'PDF' and not pdf_file and not self.instance.pdf_file:
            self.add_error('pdf_file', 'Please select a PDF document to upload.')

        if content_type == 'VIDEO' and not video_file and not youtube_url and not self.instance.video_file and not self.instance.youtube_url:
            self.add_error('youtube_url', 'Please provide a video file or streaming link (YouTube/Vimeo).')

        return cleaned_data


from .models import AboutContent, ContactInfo, HowToGuide, HowToStep


class AboutContentForm(forms.ModelForm):
    class Meta:
        model = AboutContent
        fields = [
            'eyebrow',
            'heading',
            'subheading',
            'story_title',
            'story_paragraph_1',
            'story_paragraph_2',
            'pillars_title',
            'pillars_content',
            'stat_students',
            'stat_pass_rate',
            'stat_papers',
            'stat_hours',
        ]
        widgets = {
            'eyebrow': forms.TextInput(attrs={'class': 'form-input'}),
            'heading': forms.TextInput(attrs={'class': 'form-input'}),
            'subheading': forms.TextInput(attrs={'class': 'form-input'}),
            'story_title': forms.TextInput(attrs={'class': 'form-input'}),
            'story_paragraph_1': forms.Textarea(attrs={'class': 'form-input', 'rows': 4}),
            'story_paragraph_2': forms.Textarea(attrs={'class': 'form-input', 'rows': 4}),
            'pillars_title': forms.TextInput(attrs={'class': 'form-input'}),
            'pillars_content': forms.Textarea(attrs={'class': 'form-input', 'rows': 5, 'placeholder': 'Enter core pillars (one per line)...'}),
            'stat_students': forms.TextInput(attrs={'class': 'form-input'}),
            'stat_pass_rate': forms.TextInput(attrs={'class': 'form-input'}),
            'stat_papers': forms.TextInput(attrs={'class': 'form-input'}),
            'stat_hours': forms.TextInput(attrs={'class': 'form-input'}),
        }


class ContactInfoForm(forms.ModelForm):
    class Meta:
        model = ContactInfo
        fields = [
            'phone_number',
            'whatsapp_number',
            'email_address',
            'support_email',
            'physical_address',
            'operating_hours',
            'whatsapp_community_url',
            'contact_notice',
            'facebook_url',
            'instagram_url',
            'linkedin_url',
        ]
        widgets = {
            'phone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'whatsapp_number': forms.TextInput(attrs={'class': 'form-input'}),
            'email_address': forms.EmailInput(attrs={'class': 'form-input'}),
            'support_email': forms.EmailInput(attrs={'class': 'form-input'}),
            'physical_address': forms.TextInput(attrs={'class': 'form-input'}),
            'operating_hours': forms.TextInput(attrs={'class': 'form-input'}),
            'whatsapp_community_url': forms.URLInput(attrs={'class': 'form-input'}),
            'contact_notice': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'facebook_url': forms.URLInput(attrs={'class': 'form-input'}),
            'instagram_url': forms.URLInput(attrs={'class': 'form-input'}),
            'linkedin_url': forms.URLInput(attrs={'class': 'form-input'}),
        }


class HowToStepForm(forms.ModelForm):
    class Meta:
        model = HowToStep
        fields = [
            'guide',
            'step_number',
            'badge',
            'title',
            'icon_class',
            'description',
            'call_to_action_text',
            'call_to_action_url',
            'order',
        ]
        widgets = {
            'guide': forms.Select(attrs={'class': 'form-input'}),
            'step_number': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'badge': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'STEP 1'}),
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Step Title'}),
            'icon_class': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'fa-solid fa-user-plus'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'call_to_action_text': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Enrol Now'}),
            'call_to_action_url': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '/accounts/register/'}),
            'order': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
        }

