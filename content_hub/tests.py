import os
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from accounts.models import CustomUser
from content_hub.models import Subject, ContentItem, Course, TermsContent
from wallet.models import StudentWallet, ContentUnlock


class ContentSecurityTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.subject = Subject.objects.create(name='Test Subject', slug='test-subject')
        
        # Create a valid minimal PDF file
        pdf_dir = os.path.join(settings.MEDIA_ROOT, 'protected_pdfs')
        os.makedirs(pdf_dir, exist_ok=True)
        self.pdf_file_path = os.path.join(pdf_dir, 'test_mock.pdf')
        pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 50 >>
stream
BT
/F1 18 Tf
72 700 Td
(Test Document) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000060 00000 n 
0000000118 00000 n 
0000000236 00000 n 
0000000336 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
434
%%EOF"""
        with open(self.pdf_file_path, 'wb') as f:
            f.write(pdf_content)

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

        # Now test page render - served as protected image to prevent downloads
        page_url = reverse('content_hub:render_pdf_page', kwargs={'item_slug': self.item.slug, 'page_number': 1})
        page_response = self.client.get(page_url)
        self.assertEqual(page_response.status_code, 200)
        self.assertEqual(page_response['Content-Type'], 'image/jpeg')

        # Stream URL redirects to protected viewer
        stream_url = reverse('content_hub:stream_pdf', kwargs={'item_slug': self.item.slug})
        stream_response = self.client.get(stream_url)
        self.assertEqual(stream_response.status_code, 302)

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


class CourseBundleTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.subject = Subject.objects.create(name='Mathematics', slug='mathematics')
        
        self.tutor = CustomUser.objects.create_user(
            email='tutor@example.com',
            password='Password123!',
            is_tutor=True
        )
        self.tutor_wallet = StudentWallet.objects.get(user=self.tutor)
        self.tutor_wallet.credit_coins(100)

        self.admin_user = CustomUser.objects.create_user(
            email='admin@example.com',
            password='Password123!',
            is_staff=True,
            is_admin_role=True
        )

        self.student = CustomUser.objects.create_user(
            email='learner@example.com',
            password='Password123!',
            is_student=True
        )
        self.student_wallet = StudentWallet.objects.get(user=self.student)
        self.student_wallet.credit_coins(200)

        # Create 3 items (40 coins each)
        self.item1 = ContentItem.objects.create(
            title='Calculus Limits Video',
            slug='calc-limits-video',
            subject=self.subject,
            grade='Grade 12',
            curriculum='CAPS & IEB',
            content_type='VIDEO',
            is_free=False,
            coin_price=40
        )
        self.item2 = ContentItem.objects.create(
            title='Calculus Derivatives PDF',
            slug='calc-derivatives-pdf',
            subject=self.subject,
            grade='Grade 12',
            curriculum='CAPS & IEB',
            content_type='PDF',
            is_free=False,
            coin_price=40
        )
        self.item3 = ContentItem.objects.create(
            title='Calculus Past Exam Memo PDF',
            slug='calc-memo-pdf',
            subject=self.subject,
            grade='Grade 12',
            curriculum='CAPS & IEB',
            content_type='PDF',
            is_free=False,
            coin_price=40
        )

    def test_dynamic_bundle_discounting(self):
        from content_hub.models import Course
        course = Course.objects.create(
            creator=self.tutor,
            title='Grade 12 Complete Calculus Masterclass',
            subject=self.subject,
            grade='Grade 12',
            curriculum='CAPS & IEB',
            bundle_price=100,
            status='APPROVED'
        )
        course.items.add(self.item1, self.item2, self.item3)

        # Baseline: Learner has 0 items owned
        pricing = course.get_pricing_for_user(self.student)
        self.assertEqual(pricing['final_price'], 100)
        self.assertEqual(pricing['owned_items_count'], 0)
        self.assertFalse(pricing['is_fully_owned'])

        # Now student buys item1 individually (40 coins)
        ContentUnlock.objects.create(user=self.student, content_item=self.item1, coins_spent=40)

        # Check bundle dynamic price: 100 - 40 = 60 coins!
        pricing = course.get_pricing_for_user(self.student)
        self.assertEqual(pricing['owned_items_count'], 1)
        self.assertEqual(pricing['owned_items_value'], 40)
        self.assertEqual(pricing['final_price'], 60)
        self.assertFalse(pricing['is_fully_owned'])

        # Student also buys item2 (40 coins)
        ContentUnlock.objects.create(user=self.student, content_item=self.item2, coins_spent=40)
        pricing = course.get_pricing_for_user(self.student)
        self.assertEqual(pricing['owned_items_count'], 2)
        self.assertEqual(pricing['owned_items_value'], 80)
        self.assertEqual(pricing['final_price'], 20)

        # Student unlocks the remaining item3: bundle is fully complete!
        ContentUnlock.objects.create(user=self.student, content_item=self.item3, coins_spent=40)
        pricing = course.get_pricing_for_user(self.student)
        self.assertTrue(pricing['is_fully_owned'])
        self.assertEqual(pricing['final_price'], 0)

    def test_tutor_course_creation_fee_and_queue(self):
        from content_hub.models import Course
        self.client.login(username='tutor@example.com', password='Password123!')

        url = reverse('content_hub:tutor_course_create')
        initial_balance = self.tutor_wallet.coins
        self.assertEqual(initial_balance, 100)

        post_data = {
            'title': 'New Tutor Course Bundle',
            'subject': self.subject.id,
            'grade': 'Grade 12',
            'curriculum': 'CAPS & IEB',
            'bundle_price': 90,
            'cover_svg_name': 'caps-g12-maths.svg',
            'description': 'Tutor syllabus test description',
            'items': [self.item1.id, self.item2.id],
        }

        resp = self.client.post(url, post_data)
        self.assertEqual(resp.status_code, 302)

        # Check that 50 coins were deducted
        self.tutor_wallet.refresh_from_db()
        self.assertEqual(self.tutor_wallet.coins, 50)

        # Course should be created with status PENDING
        course = Course.objects.get(title='New Tutor Course Bundle')
        self.assertEqual(course.status, 'PENDING')
        self.assertEqual(course.items.count(), 2)

    def test_admin_course_approval_and_rejection_refund(self):
        from content_hub.models import Course
        course = Course.objects.create(
            creator=self.tutor,
            title='Pending Approval Course',
            subject=self.subject,
            grade='Grade 12',
            curriculum='CAPS & IEB',
            bundle_price=80,
            creation_fee_coins=50,
            status='PENDING'
        )
        self.tutor_wallet.coins = 50
        self.tutor_wallet.save()

        # Admin logs in
        self.client.login(username='admin@example.com', password='Password123!')
        approvals_url = reverse('content_hub:admin_course_approvals')

        # Test Reject -> should refund 50 coins
        resp = self.client.post(approvals_url, {
            'course_id': course.id,
            'action': 'reject',
            'admin_notes': 'Please add more worksheets.',
        })
        self.assertEqual(resp.status_code, 302)

        course.refresh_from_db()
        self.assertEqual(course.status, 'REJECTED')
        self.tutor_wallet.refresh_from_db()
        self.assertEqual(self.tutor_wallet.coins, 100)  # 50 + 50 refunded

        # Reset to PENDING and test Approve
        course.status = 'PENDING'
        course.save()

        resp2 = self.client.post(approvals_url, {
            'course_id': course.id,
            'action': 'approve',
        })
        self.assertEqual(resp2.status_code, 302)

        course.refresh_from_db()
        self.assertEqual(course.status, 'APPROVED')

    def test_student_unlock_course_bundle(self):
        from content_hub.models import Course
        from wallet.models import CourseUnlock
        course = Course.objects.create(
            creator=self.tutor,
            title='Live Calculus Bundle',
            subject=self.subject,
            grade='Grade 12',
            curriculum='CAPS & IEB',
            bundle_price=100,
            status='APPROVED'
        )
        course.items.add(self.item1, self.item2)

        # Student already owns item1 (40c)
        ContentUnlock.objects.create(user=self.student, content_item=self.item1, coins_spent=40)

        # Student unlocks course bundle
        self.client.login(username='learner@example.com', password='Password123!')
        unlock_url = reverse('wallet:unlock_course', kwargs={'course_slug': course.slug})

        # Dynamic price is 100 - 40 = 60 coins
        self.student_wallet.refresh_from_db()
        initial_student_coins = self.student_wallet.coins

        resp = self.client.post(unlock_url)
        self.assertEqual(resp.status_code, 302)

        self.student_wallet.refresh_from_db()
        self.assertEqual(self.student_wallet.coins, initial_student_coins - 60)

        # Verify CourseUnlock created
        self.assertTrue(CourseUnlock.objects.filter(user=self.student, course=course).exists())

        # Verify bundled item2 was also unlocked for student
        self.assertTrue(ContentUnlock.objects.filter(user=self.student, content_item=self.item2).exists())


class SiteContentCMSTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = CustomUser.objects.create_user(
            email='admin_cms@example.com',
            password='Password123!',
            is_staff=True,
            is_admin_role=True
        )
        self.student = CustomUser.objects.create_user(
            email='student_cms@example.com',
            password='Password123!',
            is_student=True
        )

    def test_about_page_renders_from_db(self):
        from content_hub.models import AboutContent
        about = AboutContent.get_solo()
        about.heading = "CUSTOM DB ACADEMIC EXCELLENCE"
        about.stat_students = "999+"
        about.save()

        resp = self.client.get(reverse('about'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "CUSTOM DB ACADEMIC EXCELLENCE")
        self.assertContains(resp, "999+")

    def test_contact_page_renders_from_db_and_ajax(self):
        from content_hub.models import ContactInfo
        contact = ContactInfo.get_solo()
        contact.phone_number = "+27 88 777 6655"
        contact.email_address = "custom_contact@rodztutoring.co.za"
        contact.save()

        # Public GET
        resp = self.client.get(reverse('contact'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "+27 88 777 6655")
        self.assertContains(resp, "custom_contact@rodztutoring.co.za")

        # AJAX message submission for SweetAlert2
        ajax_resp = self.client.post(
            reverse('contact'),
            {
                'name': 'Thabo Mokoena',
                'email': 'thabo@example.com',
                'subject': 'Tutoring Inquiry',
                'message': 'I would like Grade 11 Maths tutoring.'
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(ajax_resp.status_code, 200)
        data = ajax_resp.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('Thabo', data['message'])

    def test_how_to_page_renders_steps(self):
        from content_hub.models import HowToGuide, HowToStep
        guide, _ = HowToGuide.objects.get_or_create(slug='how-it-works', defaults={'title': 'How It Works Guide'})
        guide.steps.all().delete()
        step = HowToStep.objects.create(
            guide=guide,
            step_number=1,
            badge='STEP 1',
            title='Fast Registration Walkthrough',
            icon_class='fa-solid fa-bolt',
            description='Register in seconds.',
            call_to_action_text='Get Started',
            call_to_action_url='/accounts/register/',
            order=1
        )

        resp = self.client.get(reverse('how_to'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Fast Registration Walkthrough')
        self.assertContains(resp, 'fa-bolt')

    def test_admin_cms_ajax_save_and_permissions(self):
        from content_hub.models import AboutContent, ContactInfo, HowToGuide, HowToStep
        cms_url = reverse('content_hub:admin_site_content')

        # Non-admin student blocked (403)
        self.client.login(username='student_cms@example.com', password='Password123!')
        student_resp = self.client.get(cms_url)
        self.assertEqual(student_resp.status_code, 403)

        # Admin logs in
        self.client.login(username='admin_cms@example.com', password='Password123!')
        admin_resp = self.client.get(cms_url)
        self.assertEqual(admin_resp.status_code, 200)

        # 1. AJAX Save About
        save_about_resp = self.client.post(
            cms_url,
            {
                'action': 'save_about',
                'eyebrow': 'UPDATED EYEBROW',
                'heading': 'NEW HEADLINE',
                'subheading': 'New subhead',
                'story_title': 'New Story',
                'story_paragraph_1': 'Paragraph 1 test',
                'story_paragraph_2': 'Paragraph 2 test',
                'pillars_title': 'Pillars Title',
                'pillars_content': 'Pillar 1: Details\nPillar 2: More details',
                'stat_students': '750+',
                'stat_pass_rate': '98%',
                'stat_papers': '1500+',
                'stat_hours': '3000+',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(save_about_resp.status_code, 200)
        self.assertEqual(save_about_resp.json()['status'], 'success')
        about = AboutContent.get_solo()
        self.assertEqual(about.heading, 'NEW HEADLINE')
        self.assertEqual(about.stat_students, '750+')

        # 2. AJAX Save Contact
        save_contact_resp = self.client.post(
            cms_url,
            {
                'action': 'save_contact',
                'phone_number': '+27 11 222 3333',
                'whatsapp_number': '27112223333',
                'email_address': 'admin_updated@rodztutoring.co.za',
                'support_email': 'support@rodztutoring.co.za',
                'physical_address': 'Cape Town, South Africa',
                'operating_hours': 'Mon – Fri: 08:00 – 20:00',
                'contact_notice': 'Special holiday notice',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(save_contact_resp.status_code, 200)
        self.assertEqual(save_contact_resp.json()['status'], 'success')
        contact = ContactInfo.get_solo()
        self.assertEqual(contact.phone_number, '+27 11 222 3333')
        self.assertEqual(contact.physical_address, 'Cape Town, South Africa')

        # 3. AJAX Save Step
        guide = HowToGuide.objects.get(slug='how-it-works')
        save_step_resp = self.client.post(
            cms_url,
            {
                'action': 'save_step',
                'guide': guide.id,
                'step_number': 9,
                'badge': 'STEP 9',
                'title': 'New Exam Revision Step',
                'icon_class': 'fa-solid fa-medal',
                'description': 'Revise with real examiners.',
                'order': 9,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(save_step_resp.status_code, 200)
        data = save_step_resp.json()
        self.assertEqual(data['status'], 'success')
        new_step_id = data['step']['id']

        # 4. AJAX Delete Step
        del_step_resp = self.client.post(
            cms_url,
            {
                'action': 'delete_step',
                'step_id': new_step_id,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(del_step_resp.status_code, 200)
        self.assertEqual(del_step_resp.json()['status'], 'success')
        self.assertFalse(HowToStep.objects.filter(id=new_step_id).exists())


class VideoStreamingTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.subject = Subject.objects.create(name='Physics', slug='physics')
        self.student = CustomUser.objects.create_user(
            email='videostudent@example.com',
            password='Password123!',
            is_student=True
        )

        self.free_yt_video = ContentItem.objects.create(
            title='Free YouTube Physics Stream',
            slug='free-yt-physics-stream',
            subject=self.subject,
            grade='Grade 12',
            curriculum='CAPS',
            content_type='VIDEO',
            is_free=True,
            coin_price=0,
            youtube_url='https://www.youtube.com/watch?v=2WS1dQ9-Bl8'
        )

        self.vimeo_video = ContentItem.objects.create(
            title='Free Vimeo Calculus Lesson',
            slug='free-vimeo-calculus-lesson',
            subject=self.subject,
            grade='Grade 12',
            curriculum='CAPS',
            content_type='VIDEO',
            is_free=True,
            coin_price=0,
            youtube_url='https://vimeo.com/76979871'
        )

        self.direct_mp4_video = ContentItem.objects.create(
            title='Direct MP4 Work Energy Video',
            slug='direct-mp4-work-energy',
            subject=self.subject,
            grade='Grade 12',
            curriculum='CAPS',
            content_type='VIDEO',
            is_free=True,
            coin_price=0,
            youtube_url='https://example.com/videos/lesson.mp4'
        )

        self.paid_video = ContentItem.objects.create(
            title='Paid Premium Video Pack',
            slug='paid-premium-video-pack',
            subject=self.subject,
            grade='Grade 12',
            curriculum='CAPS',
            content_type='VIDEO',
            is_free=False,
            coin_price=35,
            youtube_url='https://www.youtube.com/watch?v=9vKqVkMQHKk'
        )

    def test_youtube_embed_rendering_and_security(self):
        self.client.login(email='videostudent@example.com', password='Password123!')
        url = reverse('content_hub:view_content', kwargs={'item_slug': self.free_yt_video.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'https://www.youtube.com/embed/2WS1dQ9-Bl8')
        self.assertContains(response, 'strict-origin-when-cross-origin')
        self.assertContains(response, 'allowfullscreen')
        self.assertContains(response, 'video-player-container')

    def test_vimeo_video_rendering(self):
        self.client.login(email='videostudent@example.com', password='Password123!')
        url = reverse('content_hub:view_content', kwargs={'item_slug': self.vimeo_video.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'https://player.vimeo.com/video/76979871')

    def test_direct_mp4_video_rendering(self):
        self.client.login(email='videostudent@example.com', password='Password123!')
        url = reverse('content_hub:view_content', kwargs={'item_slug': self.direct_mp4_video.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<video')
        self.assertContains(response, 'controlsList="nodownload"')
        self.assertContains(response, 'https://example.com/videos/lesson.mp4')

    def test_locked_video_requires_unlock(self):
        self.client.login(email='videostudent@example.com', password='Password123!')
        url = reverse('content_hub:view_content', kwargs={'item_slug': self.paid_video.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Should render locked screen
        self.assertContains(response, 'PREMIUM PROTECTED CONTENT')
        self.assertContains(response, '35 Coins')
        self.assertNotContains(response, 'https://www.youtube.com/embed/9vKqVkMQHKk')


class CourseBundleBreakdownTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tutor = CustomUser.objects.create_user(
            email='tutor_breakdown@example.com',
            password='Password123!',
            is_tutor=True
        )
        self.student = CustomUser.objects.create_user(
            email='student_breakdown@example.com',
            password='Password123!',
            is_student=True
        )
        self.subject = Subject.objects.create(name='Physics', slug='physics')

        # Create Course
        self.course = Course.objects.create(
            creator=self.tutor,
            title='Grade 12 Physics Complete Exam Masterclass',
            slug='g12-physics-exam-masterclass',
            subject=self.subject,
            grade='Grade 12',
            curriculum='CAPS',
            bundle_price=250,
            status='APPROVED'
        )

        # Add 10 Videos
        self.videos = []
        for i in range(1, 11):
            vid = ContentItem.objects.create(
                title=f'Physics Video Lesson {i}',
                slug=f'physics-vid-{i}',
                subject=self.subject,
                grade='Grade 12',
                content_type='VIDEO',
                category='Video Lessons',
                coin_price=20,
                youtube_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ'
            )
            self.videos.append(vid)

        # Add 3 Question Papers
        self.question_papers = []
        for i in range(1, 4):
            qp = ContentItem.objects.create(
                title=f'Physics Past Exam Paper {i}',
                slug=f'physics-past-paper-{i}',
                subject=self.subject,
                grade='Grade 12',
                content_type='PDF',
                category='Past Papers',
                coin_price=25
            )
            self.question_papers.append(qp)

        # Add 5 Quizzes
        self.quizzes = []
        for i in range(1, 6):
            qz = ContentItem.objects.create(
                title=f'Physics Topic Quiz {i}',
                slug=f'physics-quiz-{i}',
                subject=self.subject,
                grade='Grade 12',
                content_type='QUIZ',
                category='Quiz',
                coin_price=15
            )
            self.quizzes.append(qz)

        # Add 3 Reading PDFs
        self.reading_pdfs = []
        for i in range(1, 4):
            pdf = ContentItem.objects.create(
                title=f'Physics Theory Notes {i}',
                slug=f'physics-reading-pdf-{i}',
                subject=self.subject,
                grade='Grade 12',
                content_type='PDF',
                category='Notes',
                coin_price=20
            )
            self.reading_pdfs.append(pdf)

        # Attach all items to course
        all_items = self.videos + self.question_papers + self.quizzes + self.reading_pdfs
        self.course.items.set(all_items)

    def test_bundle_counts_exact_breakdown(self):
        counts = self.course.bundle_counts
        self.assertEqual(counts['videos'], 10)
        self.assertEqual(counts['question_papers'], 3)
        self.assertEqual(counts['quizzes'], 5)
        self.assertEqual(counts['reading_pdfs'], 3)
        self.assertEqual(counts['other'], 0)

        self.assertEqual(self.course.video_count, 10)
        self.assertEqual(self.course.question_paper_count, 3)
        self.assertEqual(self.course.quiz_count, 5)
        self.assertEqual(self.course.reading_pdf_count, 3)

    def test_bundle_breakdown_structure_and_labels(self):
        breakdown = self.course.bundle_breakdown
        labels = [item['label'] for item in breakdown]
        self.assertIn('10 Videos', labels)
        self.assertIn('3 Question Papers', labels)
        self.assertIn('5 Quizzes', labels)
        self.assertIn('3 Reading PDFs', labels)

        self.assertEqual(
            self.course.bundle_summary_text,
            '10 Videos, 3 Question Papers, 5 Quizzes, 3 Reading PDFs'
        )

    def test_singular_plural_grammar(self):
        single_course = Course.objects.create(
            creator=self.tutor,
            title='Single Item Sampler Course',
            slug='single-item-sampler',
            subject=self.subject,
            bundle_price=50,
            status='APPROVED'
        )
        single_course.items.add(self.videos[0])
        single_course.items.add(self.question_papers[0])
        single_course.items.add(self.quizzes[0])
        single_course.items.add(self.reading_pdfs[0])

        breakdown = single_course.bundle_breakdown
        labels = [item['label'] for item in breakdown]
        self.assertIn('1 Video', labels)
        self.assertIn('1 Question Paper', labels)
        self.assertIn('1 Quiz', labels)
        self.assertIn('1 Reading PDF', labels)
        self.assertEqual(
            single_course.bundle_summary_text,
            '1 Video, 1 Question Paper, 1 Quiz, 1 Reading PDF'
        )

    def test_catalog_and_course_detail_html_rendering(self):
        # 1. Catalog page should render the breakdown badges
        catalog_url = reverse('content_hub:catalog')
        res_cat = self.client.get(catalog_url)
        self.assertEqual(res_cat.status_code, 200)
        self.assertContains(res_cat, '10 Videos')
        self.assertContains(res_cat, '3 Question Papers')
        self.assertContains(res_cat, '5 Quizzes')
        self.assertContains(res_cat, '3 Reading PDFs')

        # 2. Course Detail page should render the breakdown badges in header and sidebar
        detail_url = reverse('content_hub:course_detail', kwargs={'slug': self.course.slug})
        res_detail = self.client.get(detail_url)
        self.assertEqual(res_detail.status_code, 200)
        self.assertContains(res_detail, "What's included in this bundle")
        self.assertContains(res_detail, "Bundle Contents")
        self.assertContains(res_detail, '10 Videos')
        self.assertContains(res_detail, '3 Question Papers')
        self.assertContains(res_detail, '5 Quizzes')
        self.assertContains(res_detail, '3 Reading PDFs')


class TermsAndConditionsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = CustomUser.objects.create_superuser(
            email='admin_terms@example.com',
            password='AdminPassword123!'
        )

    def test_public_terms_page(self):
        url = reverse('content_hub:terms')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Terms of Service')
        self.assertContains(response, 'Section 1: Nature of Rodz Study Coins')
        self.assertContains(response, 'Section 2: Dynamic Pricing')
        self.assertContains(response, 'Section 3: Peer Transfers')
        self.assertContains(response, 'Section 4: Course Creator Revenue')

    def test_admin_update_terms_content(self):
        self.client.login(email='admin_terms@example.com', password='AdminPassword123!')
        url = reverse('accounts:admin_site_content')

        resp = self.client.post(url, {
            'action': 'save_terms',
            'title': 'Rodz Tutoring Updated Global Terms 2026',
            'intro_notice': 'Notice of updated fee and treasury structure.',
            'coin_policy': 'Coins are non-refundable utility tokens.',
            'pricing_policy': 'Prices can be adjusted by admins at any time.',
            'transfer_charges_policy': 'Transfer charges support system stability.',
            'creator_earnings_policy': 'Course creators earn when courses unlock.',
            'content_licensing_policy': 'Digital rights strictly protected.',
            'refund_policy': 'Refunds subject to admin review.',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        terms = TermsContent.get_solo()
        self.assertEqual(terms.title, 'Rodz Tutoring Updated Global Terms 2026')
        self.assertEqual(terms.intro_notice, 'Notice of updated fee and treasury structure.')
        self.assertEqual(terms.pricing_policy, 'Prices can be adjusted by admins at any time.')


from django.core.files.uploadedfile import SimpleUploadedFile

class FreeResourcesAndDownloadsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.subject = Subject.objects.create(name='Mathematics', slug='maths')
        self.user = CustomUser.objects.create_user(
            email='student_free@example.com',
            password='TestPassword123!'
        )
        self.tutor = CustomUser.objects.create_user(
            email='tutor_upload@example.com',
            password='TestPassword123!',
            is_tutor=True,
            tutor_status='APPROVED'
        )

        dummy_pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 50 >>
stream
BT
/F1 18 Tf
72 700 Td
(Test Document) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000060 00000 n 
0000000118 00000 n 
0000000236 00000 n 
0000000336 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
434
%%EOF"""
        self.uploaded_pdf = SimpleUploadedFile("sample_notes.pdf", dummy_pdf_content, content_type="application/pdf")

        # Free and downloadable
        self.free_downloadable = ContentItem.objects.create(
            title='Free Downloadable Past Paper',
            slug='free-downloadable-past-paper',
            subject=self.subject,
            grade='Grade 12',
            content_type='PDF',
            category='Question Paper',
            is_free=True,
            allow_download=True,
            pdf_file=self.uploaded_pdf,
            coin_price=0
        )

        # Free but not downloadable
        self.free_view_only = ContentItem.objects.create(
            title='Free View Only Guide',
            slug='free-view-only-guide',
            subject=self.subject,
            grade='Grade 12',
            content_type='PDF',
            category='Notes',
            is_free=True,
            allow_download=False,
            pdf_file=self.uploaded_pdf,
            coin_price=0
        )

        # Paid item
        self.paid_item = ContentItem.objects.create(
            title='Paid Exam Solution',
            slug='paid-exam-solution',
            subject=self.subject,
            grade='Grade 12',
            content_type='PDF',
            category='Notes',
            is_free=False,
            allow_download=False,
            pdf_file=self.uploaded_pdf,
            coin_price=50
        )

    def test_how_to_page_shows_free_resources_information(self):
        url = reverse('content_hub:how_to')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Free Study Resources Available')
        self.assertContains(response, 'Start Learning Right Now Without Buying Coins')
        self.assertContains(response, 'BROWSE FREE STUDY RESOURCES')

    def test_tutoring_page_copy_and_welcoming_hero(self):
        url = reverse('content_hub:tutoring')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Check welcoming hero and scroll prompt
        self.assertContains(response, 'Welcome to Rodz Tutoring')
        self.assertContains(response, 'Scroll Down to Check Tutoring Options')
        # Check that courses is replaced with tutoring
        self.assertContains(response, 'INTENSIVE REVISION TUTORING')
        self.assertContains(response, 'BOOK EXAM REVISION TUTORING')
        # Ensure no old crash course button text
        self.assertNotContains(response, 'BOOK EXAM CRASH COURSE')

    def test_download_free_allowed_item(self):
        url = reverse('content_hub:download_content', kwargs={'item_slug': self.free_downloadable.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.get('Content-Disposition', ''))

    def test_download_free_disallowed_item_is_forbidden(self):
        url = reverse('content_hub:download_content', kwargs={'item_slug': self.free_view_only.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_download_paid_item_is_strictly_forbidden(self):
        url = reverse('content_hub:download_content', kwargs={'item_slug': self.paid_item.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_upload_resource_view_student_forbidden(self):
        self.client.login(email='student_free@example.com', password='TestPassword123!')
        url = reverse('content_hub:upload_resource')
        response = self.client.get(url)
        # Students redirected to dashboard
        self.assertEqual(response.status_code, 302)

    def test_upload_resource_view_tutor_allowed(self):
        self.client.login(email='tutor_upload@example.com', password='TestPassword123!')
        url = reverse('content_hub:upload_resource')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'UPLOAD STUDY RESOURCE')
        self.assertContains(response, 'Allow learners to download this file directly')

    def test_anonymous_user_can_view_free_content_without_login(self):
        self.client.logout()
        url = reverse('content_hub:view_content', kwargs={'item_slug': self.free_view_only.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Free Educational Resource')
        self.assertContains(response, self.free_view_only.title)

    def test_anonymous_user_can_render_free_pdf_page_without_login(self):
        self.client.logout()
        url = reverse('content_hub:render_pdf_page', kwargs={'item_slug': self.free_view_only.slug, 'page_number': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')

    def test_anonymous_user_can_download_free_item_without_login(self):
        self.client.logout()
        url = reverse('content_hub:download_content', kwargs={'item_slug': self.free_downloadable.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.get('Content-Disposition', ''))

    def test_anonymous_user_viewing_paid_content_redirects_to_login(self):
        self.client.logout()
        url = reverse('content_hub:view_content', kwargs={'item_slug': self.paid_item.slug})
        response = self.client.get(url)
        # Should redirect anonymous user to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_anonymous_user_rendering_paid_content_is_forbidden(self):
        self.client.logout()
        url = reverse('content_hub:render_pdf_page', kwargs={'item_slug': self.paid_item.slug, 'page_number': 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


class SeedCommandTest(TestCase):
    def test_seed_rodz_populates_all_models_and_is_idempotent(self):
        import tempfile
        from io import StringIO
        from django.core.management import call_command
        from django.test import override_settings
        from content_hub.models import (
            AboutContent,
            ContactInfo,
            Curriculum,
            HowToGuide,
            HowToStep,
        )
        from quizzes.models import Choice, Question, Quiz, QuizAttempt
        from wallet.models import (
            CoinBundle,
            CoinPaymentRequest,
            CoinPriceChangeLog,
            CoinTransaction,
            ContentUnlock,
            CourseUnlock,
            PaymentMethod,
            StudentWallet,
            SystemWallet,
        )

        with tempfile.TemporaryDirectory() as tmp_media:
            with override_settings(MEDIA_ROOT=tmp_media):
                out = StringIO()
                call_command('seed_rodz', stdout=out)

                # Verify >= 10 objects on all multi-record models
                model_classes = [
                    CustomUser,
                    Curriculum,
                    Subject,
                    ContentItem,
                    Course,
                    HowToGuide,
                    HowToStep,
                    Quiz,
                    Question,
                    Choice,
                    QuizAttempt,
                    StudentWallet,
                    CoinBundle,
                    PaymentMethod,
                    CoinTransaction,
                    ContentUnlock,
                    CourseUnlock,
                    CoinPaymentRequest,
                    CoinPriceChangeLog,
                ]
                first_counts = {cls.__name__: cls.objects.count() for cls in model_classes}
                for name, count in first_counts.items():
                    self.assertGreaterEqual(count, 10, f"Expected >= 10 records for {name}, got {count}")

                # Verify singletons exist cleanly
                self.assertEqual(AboutContent.objects.count(), 1)
                self.assertEqual(ContactInfo.objects.count(), 1)
                self.assertEqual(TermsContent.objects.count(), 1)
                self.assertEqual(SystemWallet.objects.count(), 1)

                # Verify every user type & tutor status exists, authenticates, and loads dashboard cleanly
                test_accounts = [
                    ('admin@rodztutoring.co.za', 'RodzAdmin2026!'),
                    ('operations@rodztutoring.co.za', 'RodzAdmin2026!'),
                    ('tutor@rodztutoring.co.za', 'RodzTutor2026!'),
                    ('peer.tutor1@rodztutoring.co.za', 'RodzTutor2026!'),
                    ('applicant.pending1@rodztutoring.co.za', 'RodzStudent2026!'),
                    ('applicant.rejected1@rodztutoring.co.za', 'RodzStudent2026!'),
                    ('student@rodztutoring.co.za', 'RodzStudent2026!'),
                ]
                dashboard_url = reverse('accounts:dashboard')
                for email, pwd in test_accounts:
                    self.assertTrue(self.client.login(email=email, password=pwd), f"Login failed for {email}")
                    dash_resp = self.client.get(dashboard_url)
                    self.assertEqual(dash_resp.status_code, 200, f"Dashboard failed for {email}")

                student_coins_before = StudentWallet.objects.get(user__email='student@rodztutoring.co.za').coins

                # Run seed_rodz a second time to verify strict idempotency
                call_command('seed_rodz', stdout=StringIO())

                second_counts = {cls.__name__: cls.objects.count() for cls in model_classes}
                self.assertEqual(first_counts, second_counts)
                self.assertEqual(
                    StudentWallet.objects.get(user__email='student@rodztutoring.co.za').coins,
                    student_coins_before,
                )










