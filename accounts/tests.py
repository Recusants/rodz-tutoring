from django.test import TestCase, Client
from accounts.models import CustomUser


class AccountsTestCase(TestCase):
    def test_create_user_with_email(self):
        user = CustomUser.objects.create_user(
            email='testlearner@example.com',
            password='StrongPassword123!',
            full_name='Test Learner',
            is_student=True,
            is_tutor=False
        )
        self.assertEqual(user.email, 'testlearner@example.com')
        self.assertTrue(user.check_password('StrongPassword123!'))
        self.assertTrue(user.is_student)
        self.assertFalse(user.is_tutor)
        self.assertEqual(user.roles_display, 'Student')

    def test_multi_role_user(self):
        # Combination of Student and Tutor
        user = CustomUser.objects.create_user(
            email='senior@example.com',
            password='StrongPassword123!',
            is_student=True,
            is_tutor=True
        )
        self.assertTrue(user.is_student)
        self.assertTrue(user.is_tutor)
        self.assertIn('Student', user.roles_display)
        self.assertIn('Tutor', user.roles_display)

    def test_login_post(self):
        user = CustomUser.objects.create_user(
            email='loginuser@example.com',
            password='MyPassword123!'
        )
        response = self.client.post('/accounts/login/', {
            'email': 'loginuser@example.com',
            'password': 'MyPassword123!'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertEqual(response.context['user'].email, 'loginuser@example.com')

    def test_profile_update(self):
        user = CustomUser.objects.create_user(
            email='profileuser@example.com',
            password='MyPassword123!',
            full_name='Old Name'
        )
        self.client.login(username='profileuser@example.com', password='MyPassword123!')
        response = self.client.post('/accounts/profile/', {
            'action': 'update_profile',
            'full_name': 'New Student Name',
            'phone_number': '+27 74 999 8888',
            'grade': 'Grade 11',
            'curriculum': 'IEB',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.full_name, 'New Student Name')
        self.assertEqual(user.curriculum, 'IEB')

    def test_password_reset_request(self):
        from django.core import mail
        user = CustomUser.objects.create_user(
            email='resetuser@example.com',
            password='Password123!'
        )
        response = self.client.post('/accounts/password-reset/', {
            'email': 'resetuser@example.com'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Reset Your Account Password', mail.outbox[0].subject)

    def test_system_settings_permission_blocked_for_normal_student(self):
        user = CustomUser.objects.create_user(
            email='normalstudent@example.com',
            password='Password123!',
            is_student=True,
            is_admin_role=False,
            is_staff=False
        )
        self.client.login(username='normalstudent@example.com', password='Password123!')
        response = self.client.get('/accounts/system-settings/')
        # Non-admin should be redirected or blocked
        self.assertNotEqual(response.status_code, 200)

    def test_system_settings_accessible_by_admin(self):
        admin = CustomUser.objects.create_user(
            email='staffadmin@example.com',
            password='Password123!',
            is_admin_role=True,
            is_staff=True
        )
        self.client.login(username='staffadmin@example.com', password='Password123!')
        response = self.client.get('/accounts/system-settings/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SYSTEM CONFIGURATION MANAGEMENT')

    def test_mode_switching_for_multi_role_user(self):
        # User with Student + Tutor + Admin
        multi_user = CustomUser.objects.create_user(
            email='multiuser@example.com',
            password='Password123!',
            is_student=True,
            is_tutor=True,
            is_admin_role=True
        )
        self.client.login(username='multiuser@example.com', password='Password123!')

        # Default mode should be admin
        self.assertEqual(multi_user.default_role_mode, 'admin')

        # Switch to student mode
        res = self.client.get('/accounts/switch-mode/student/', follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.session.get('active_role_mode'), 'student')

        # Switch to tutor mode
        res = self.client.get('/accounts/switch-mode/tutor/', follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.session.get('active_role_mode'), 'tutor')

        # Try to switch to invalid role
        res = self.client.get('/accounts/switch-mode/astronaut/', follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertNotEqual(self.client.session.get('active_role_mode'), 'astronaut')

    def test_admin_user_directory_and_detail_controls(self):
        admin = CustomUser.objects.create_user(
            email='supercontroller@example.com',
            password='Password123!',
            is_admin_role=True,
            is_staff=True
        )
        target = CustomUser.objects.create_user(
            email='targetstudent@example.com',
            password='OldPass123!',
            full_name='Target Student',
            grade='Grade 10',
            is_student=True
        )

        self.client.login(username='supercontroller@example.com', password='Password123!')

        # 1. Directory View
        dir_res = self.client.get('/accounts/admin/users/')
        self.assertEqual(dir_res.status_code, 200)
        self.assertContains(dir_res, 'targetstudent@example.com')

        # 2. Edit Profile
        edit_res = self.client.post(f'/accounts/admin/users/{target.id}/', {
            'action': 'edit_profile',
            'email': 'targetstudent@example.com',
            'full_name': 'Updated Target Learner',
            'phone_number': '+27 82 555 1234',
            'grade': 'Grade 12',
            'curriculum': 'CAPS',
            'is_student': True,
            'is_tutor': True,  # Grant tutor role
            'is_active': True,
        }, follow=True)
        self.assertEqual(edit_res.status_code, 200)
        target.refresh_from_db()
        self.assertEqual(target.full_name, 'Updated Target Learner')
        self.assertEqual(target.grade, 'Grade 12')
        self.assertTrue(target.is_tutor)

        # 3. Direct Password Overwrite
        pw_res = self.client.post(f'/accounts/admin/users/{target.id}/', {
            'action': 'direct_password',
            'new_password': 'BrandNewPassword999!',
            'confirm_password': 'BrandNewPassword999!'
        }, follow=True)
        self.assertEqual(pw_res.status_code, 200)
        target.refresh_from_db()
        self.assertTrue(target.check_password('BrandNewPassword999!'))

        # 4. Wallet Adjustment (Credit & Debit)
        from wallet.models import StudentWallet
        wallet, _ = StudentWallet.objects.get_or_create(user=target)
        self.assertEqual(wallet.coins, 0)

        # Credit 150 coins
        cred_res = self.client.post(f'/accounts/admin/users/{target.id}/', {
            'action': 'adjust_wallet',
            'action_type': 'CREDIT',
            'coins': 150,
            'description': 'Scholarship grant for top marks'
        }, follow=True)
        self.assertEqual(cred_res.status_code, 200)
        wallet.refresh_from_db()
        self.assertEqual(wallet.coins, 150)

        # Debit 30 coins
        deb_res = self.client.post(f'/accounts/admin/users/{target.id}/', {
            'action': 'adjust_wallet',
            'action_type': 'DEBIT',
            'coins': 30,
            'description': 'Correction deduction'
        }, follow=True)
        self.assertEqual(deb_res.status_code, 200)
        wallet.refresh_from_db()
        self.assertEqual(wallet.coins, 120)

        # 5. Grant and Revoke Content Unlock
        from content_hub.models import ContentItem, Subject
        subject = Subject.objects.create(name='Physics', slug='physics-test')
        item = ContentItem.objects.create(
            title='Test Physics Pack',
            slug='test-physics-pack',
            subject=subject,
            grade='Grade 12',
            coin_price=60
        )

        grant_res = self.client.post(f'/accounts/admin/users/{target.id}/', {
            'action': 'grant_unlock',
            'content_item': item.id
        }, follow=True)
        self.assertEqual(grant_res.status_code, 200)
        self.assertTrue(target.has_unlocked(item))

        # Revoke unlock
        from wallet.models import ContentUnlock
        unlock = ContentUnlock.objects.get(user=target, content_item=item)
        rev_res = self.client.post(f'/accounts/admin/users/{target.id}/', {
            'action': 'revoke_unlock',
            'unlock_id': unlock.id
        }, follow=True)
        self.assertEqual(rev_res.status_code, 200)
        self.assertFalse(ContentUnlock.objects.filter(id=unlock.id).exists())

        # 6. Suspend and Reactivate
        sus_res = self.client.post(f'/accounts/admin/users/{target.id}/', {
            'action': 'toggle_status'
        }, follow=True)
        self.assertEqual(sus_res.status_code, 200)
        target.refresh_from_db()
        self.assertFalse(target.is_active)

    def test_user_registration_flow(self):
        res = self.client.post('/accounts/register/', {
            'email': 'brandnewlearner@example.com',
            'full_name': 'Brand New Student',
            'phone_number': '+27 71 234 5678',
            'grade': 'Grade 11',
            'curriculum': 'CAPS',
            'password': 'SecurePassword987!',
            'password_confirm': 'SecurePassword987!',
            'is_student': True,
        }, follow=True)
        self.assertEqual(res.status_code, 200)
        new_user = CustomUser.objects.filter(email='brandnewlearner@example.com').first()
        self.assertIsNotNone(new_user)
        self.assertTrue(new_user.is_authenticated)
        self.assertTrue(new_user.is_student)
        self.assertEqual(new_user.grade, 'Grade 11')

    def test_user_logout_flow(self):
        user = CustomUser.objects.create_user(
            email='logouttest@example.com',
            password='Password123!'
        )
        self.client.login(email='logouttest@example.com', password='Password123!')
        res = self.client.get('/accounts/logout/', follow=True)
        self.assertEqual(res.status_code, 200)
        # User should no longer be authenticated
        self.assertFalse(res.context['user'].is_authenticated)


from django.core.files.uploadedfile import SimpleUploadedFile

class TutorApprovalWorkflowTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = CustomUser.objects.create_superuser(
            email='super_tutor_admin@example.com',
            password='AdminPassword123!'
        )
        self.dummy_image = SimpleUploadedFile(
            "tutor_pic.jpg",
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9",
            content_type="image/jpeg"
        )

    def test_registration_as_tutor_without_photo_fails(self):
        res = self.client.post('/accounts/register/', {
            'email': 'tutor_nophoto@example.com',
            'full_name': 'No Photo Applicant',
            'phone_number': '+27 72 000 1111',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'is_student': True,
            'is_tutor': True,
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Please upload a profile photo for admin verification.')

    def test_registration_as_tutor_with_photo_sets_pending_status(self):
        res = self.client.post('/accounts/register/', {
            'email': 'tutor_pending@example.com',
            'full_name': 'Pending Tutor',
            'phone_number': '+27 72 123 4567',
            'grade': 'Grade 12',
            'curriculum': 'CAPS',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'is_student': True,
            'is_tutor': True,
            'profile_picture': self.dummy_image,
            'bio': 'Passionate Mathematics tutor with 5 years experience.',
        }, follow=True)

        self.assertEqual(res.status_code, 200)
        user = CustomUser.objects.get(email='tutor_pending@example.com')
        # Crucial requirement: Tutor privileges are NOT granted immediately!
        self.assertFalse(user.is_tutor)
        self.assertEqual(user.tutor_status, 'PENDING')
        self.assertIsNotNone(user.tutor_applied_at)
        self.assertTrue(user.is_student)
        self.assertTrue(bool(user.profile_picture))

    def test_student_applies_via_tutor_apply_view(self):
        student = CustomUser.objects.create_user(
            email='existing_student@example.com',
            password='Password123!',
            is_student=True,
            is_tutor=False
        )
        self.client.login(email='existing_student@example.com', password='Password123!')

        get_res = self.client.get('/accounts/tutor-apply/')
        self.assertEqual(get_res.status_code, 200)

        post_res = self.client.post('/accounts/tutor-apply/', {
            'phone_number': '+27 82 987 6543',
            'bio': 'Degree in Applied Physics, tutoring Grade 11 & 12 Physical Sciences.',
            'profile_picture': self.dummy_image
        }, follow=True)
        self.assertEqual(post_res.status_code, 200)

        student.refresh_from_db()
        self.assertEqual(student.tutor_status, 'PENDING')
        self.assertFalse(student.is_tutor)
        self.assertEqual(student.phone_number, '+27 82 987 6543')

    def test_admin_approves_tutor(self):
        applicant = CustomUser.objects.create_user(
            email='applicant_for_approval@example.com',
            password='Password123!',
            tutor_status='PENDING',
            is_tutor=False
        )
        self.client.login(email='super_tutor_admin@example.com', password='AdminPassword123!')

        resp = self.client.post('/accounts/admin/tutor-approvals/', {
            'action': 'approve',
            'user_id': applicant.id
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        applicant.refresh_from_db()
        self.assertTrue(applicant.is_tutor)
        self.assertEqual(applicant.tutor_status, 'APPROVED')
        self.assertIsNotNone(applicant.tutor_approved_at)
        self.assertEqual(applicant.tutor_reviewed_by, self.admin)

    def test_admin_rejects_tutor(self):
        applicant = CustomUser.objects.create_user(
            email='applicant_for_rejection@example.com',
            password='Password123!',
            tutor_status='PENDING',
            is_tutor=False
        )
        self.client.login(email='super_tutor_admin@example.com', password='AdminPassword123!')

        resp = self.client.post('/accounts/admin/tutor-approvals/', {
            'action': 'reject',
            'user_id': applicant.id,
            'rejection_reason': 'Photo was unclear. Please upload a clear headshot.'
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        applicant.refresh_from_db()
        self.assertFalse(applicant.is_tutor)
        self.assertEqual(applicant.tutor_status, 'REJECTED')
        self.assertEqual(applicant.tutor_rejection_reason, 'Photo was unclear. Please upload a clear headshot.')

    def test_admin_user_detail_quick_approval_and_rejection(self):
        applicant = CustomUser.objects.create_user(
            email='detail_applicant@example.com',
            password='Password123!',
            tutor_status='PENDING',
            is_tutor=False
        )
        self.client.login(email='super_tutor_admin@example.com', password='AdminPassword123!')

        # Approve via user detail view
        app_res = self.client.post(f'/accounts/admin/users/{applicant.id}/', {
            'action': 'approve_tutor'
        }, follow=True)
        self.assertEqual(app_res.status_code, 200)
        applicant.refresh_from_db()
        self.assertTrue(applicant.is_tutor)
        self.assertEqual(applicant.tutor_status, 'APPROVED')

        # Reject via user detail view
        rej_res = self.client.post(f'/accounts/admin/users/{applicant.id}/', {
            'action': 'reject_tutor',
            'rejection_reason': 'Credentials expired.'
        }, follow=True)
        self.assertEqual(rej_res.status_code, 200)
        applicant.refresh_from_db()
        self.assertFalse(applicant.is_tutor)
        self.assertEqual(applicant.tutor_status, 'REJECTED')


