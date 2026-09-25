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

        # Now stream the PDF - served as protected octet-stream to prevent downloads
        stream_url = reverse('content_hub:stream_pdf', kwargs={'item_slug': self.item.slug})
        stream_response = self.client.get(stream_url)
        self.assertEqual(stream_response.status_code, 200)
        self.assertEqual(stream_response['Content-Type'], 'application/octet-stream')
        self.assertIn('inline', stream_response['Content-Disposition'])

    def test_dynamic_curriculum(self):
        from content_hub.models import Curriculum
        cambridge = Curriculum.objects.create(name='Cambridge International', code='CAMBRIDGE')
        self.item.curriculum_ref = cambridge
        self.item.save()

        # Catalog filter by Cambridge
        resp = self.client.get(reverse('content_hub:catalog'), {'curriculum': 'CAMBRIDGE'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.item, resp.context['items'])

    def test_grade_prioritization(self):
        # Create Grade 10 and Grade 12 items
        g10_item = ContentItem.objects.create(
            title='Grade 10 Basics',
            slug='g10-basics',
            subject=self.subject,
            grade='Grade 10',
            curriculum='CAPS',
            content_type='PDF'
        )

        student_g12 = CustomUser.objects.create_user(
            email='g12student@example.com',
            password='Password123!',
            grade='Grade 12',
            is_student=True
        )

        self.client.login(username='g12student@example.com', password='Password123!')
        resp = self.client.get(reverse('content_hub:catalog'))
        self.assertEqual(resp.status_code, 200)

        # Grade 12 item should appear before Grade 10 item for Grade 12 student
        items = list(resp.context['items'])
        self.assertEqual(items[0].grade, 'Grade 12')


