import os
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from accounts.models import CustomUser
from content_hub.models import Subject, ContentItem
from wallet.models import StudentWallet, ContentUnlock


class ContentSecurityTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.subject = Subject.objects.create(name='Test Subject', slug='test-subject')
        
        # Create a mock PDF file
        pdf_dir = os.path.join(settings.MEDIA_ROOT, 'protected_pdfs')
        os.makedirs(pdf_dir, exist_ok=True)
        self.pdf_file_path = os.path.join(pdf_dir, 'test_mock.pdf')
        with open(self.pdf_file_path, 'wb') as f:
            f.write(b"%PDF-1.4\n%EOF\n")

        self.item = ContentItem.objects.create(
            title='Test Grade 12 Math Pack',
            slug='test-math-pack',
            subject=self.subject,
            grade='Grade 12',
            curriculum='CAPS & IEB',
            content_type='PDF',
            is_free=False,
            coin_price=50,
            pdf_file='protected_pdfs/test_mock.pdf'
        )

        self.student = CustomUser.objects.create_user(
            email='student_sec@example.com',
            password='Password123!',
            is_student=True
        )

    def test_unauthenticated_stream_blocked(self):
        url = reverse('content_hub:stream_pdf', kwargs={'item_slug': self.item.slug})
        response = self.client.get(url)
        # Should redirect to login
        self.assertEqual(response.status_code, 302)

    def test_authenticated_locked_stream_forbidden(self):
        self.client.login(username='student_sec@example.com', password='Password123!')
        url = reverse('content_hub:stream_pdf', kwargs={'item_slug': self.item.slug})
        response = self.client.get(url)
        # Without unlocking, stream is 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_unlocked_stream_allowed(self):
        # Give student coins & unlock
        wallet = StudentWallet.objects.get(user=self.student)
        wallet.credit_coins(100)
        
        unlock_url = reverse('wallet:unlock_item', kwargs={'item_slug': self.item.slug})
        self.client.login(username='student_sec@example.com', password='Password123!')
        
        # Unlock via POST
        post_response = self.client.post(unlock_url)
        self.assertEqual(post_response.status_code, 302)

        # Now stream the PDF
        stream_url = reverse('content_hub:stream_pdf', kwargs={'item_slug': self.item.slug})
        stream_response = self.client.get(stream_url)
        self.assertEqual(stream_response.status_code, 200)
        self.assertEqual(stream_response['Content-Type'], 'application/pdf')
        self.assertIn('inline', stream_response['Content-Disposition'])
