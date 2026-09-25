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
