from django.test import TestCase
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
