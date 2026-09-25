from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import CustomUser
from content_hub.models import Subject, ContentItem
from wallet.models import StudentWallet, ContentUnlock
from quizzes.models import Quiz, Question, Choice, QuizAttempt


class QuizzesTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.subject = Subject.objects.create(name='Mathematics', slug='mathematics')

        # Paid item
        self.paid_item = ContentItem.objects.create(
            title='Algebra Masterclass Pack',
            slug='algebra-masterclass-pack',
            subject=self.subject,
            grade='Grade 12',
            curriculum='CAPS',
            content_type='PDF',
            is_free=False,
            coin_price=40
        )

        # Free item
        self.free_item = ContentItem.objects.create(
            title='Intro to Calculus Free Pack',
            slug='intro-calculus-free',
            subject=self.subject,
            grade='Grade 12',
            curriculum='CAPS',
            content_type='PDF',
            is_free=True,
            coin_price=0
        )

        # Quizzes
        self.paid_quiz = Quiz.objects.create(
            content_item=self.paid_item,
            title='Algebra Mastery Quiz',
            instructions='Solve all equations carefully.',
            time_limit_minutes=20,
            pass_percentage=70
        )
        self.q1 = Question.objects.create(
            quiz=self.paid_quiz,
            text='What is the solution to 2x + 6 = 14?',
            explanation='2x = 8 => x = 4',
            order=1
        )
        self.c1_correct = Choice.objects.create(question=self.q1, text='x = 4', is_correct=True)
        self.c1_wrong = Choice.objects.create(question=self.q1, text='x = 5', is_correct=False)

        self.q2 = Question.objects.create(
            quiz=self.paid_quiz,
            text='What is the discriminant of x^2 - 4x + 4 = 0?',
            explanation='Delta = b^2 - 4ac = 16 - 16 = 0',
            order=2
        )
        self.c2_correct = Choice.objects.create(question=self.q2, text='0', is_correct=True)
        self.c2_wrong = Choice.objects.create(question=self.q2, text='4', is_correct=False)

        self.free_quiz = Quiz.objects.create(
            content_item=self.free_item,
            title='Calculus Fundamentals Quiz',
            instructions='Answer basic calculus questions.',
            pass_percentage=50
        )
        self.free_q1 = Question.objects.create(
            quiz=self.free_quiz,
            text='What is the derivative of x^2?',
            explanation='d/dx(x^2) = 2x',
            order=1
        )
        self.free_c1_correct = Choice.objects.create(question=self.free_q1, text='2x', is_correct=True)
        self.free_c1_wrong = Choice.objects.create(question=self.free_q1, text='x', is_correct=False)

        # Users
        self.student = CustomUser.objects.create_user(
            email='quizstudent@example.com',
            password='Password123!',
            is_student=True
        )
        self.tutor = CustomUser.objects.create_user(
            email='quiztutor@example.com',
            password='Password123!',
            is_tutor=True
        )
        self.admin = CustomUser.objects.create_superuser(
            email='quizadmin@example.com',
            password='AdminPassword123!'
        )

    def test_quiz_model_properties_and_string(self):
        self.assertEqual(self.paid_quiz.question_count, 2)
        self.assertIn('Algebra Mastery Quiz', str(self.paid_quiz))
        self.assertIn('Q2:', str(self.q1))
        self.assertIn('(Correct)', str(self.c1_correct))
        self.assertNotIn('(Correct)', str(self.c1_wrong))

    def test_unauthenticated_user_redirected_to_login(self):
        url = reverse('quizzes:take_quiz', kwargs={'quiz_id': self.paid_quiz.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_paid_quiz_locked_for_student_without_unlock(self):
        self.client.login(email='quizstudent@example.com', password='Password123!')
        url = reverse('quizzes:take_quiz', kwargs={'quiz_id': self.paid_quiz.id})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        # Should redirect student to the content item view page with warning
        self.assertIn(self.paid_item.slug, response.redirect_chain[0][0])

    def test_paid_quiz_accessible_when_unlocked_by_student(self):
        # Grant unlock
        ContentUnlock.objects.create(
            user=self.student,
            content_item=self.paid_item,
            coins_spent=40
        )
        self.client.login(email='quizstudent@example.com', password='Password123!')
        url = reverse('quizzes:take_quiz', kwargs={'quiz_id': self.paid_quiz.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Algebra Mastery Quiz')
        self.assertContains(response, 'What is the solution to 2x + 6 = 14?')

    def test_free_quiz_accessible_without_unlock(self):
        self.client.login(email='quizstudent@example.com', password='Password123!')
        url = reverse('quizzes:take_quiz', kwargs={'quiz_id': self.free_quiz.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Calculus Fundamentals Quiz')

    def test_paid_quiz_accessible_by_tutor_and_admin(self):
        # Tutor access
        self.client.login(email='quiztutor@example.com', password='Password123!')
        url = reverse('quizzes:take_quiz', kwargs={'quiz_id': self.paid_quiz.id})
        res_tutor = self.client.get(url)
        self.assertEqual(res_tutor.status_code, 200)

        # Admin access
        self.client.login(email='quizadmin@example.com', password='AdminPassword123!')
        res_admin = self.client.get(url)
        self.assertEqual(res_admin.status_code, 200)

    def test_quiz_submission_passed(self):
        ContentUnlock.objects.create(user=self.student, content_item=self.paid_item, coins_spent=40)
        self.client.login(email='quizstudent@example.com', password='Password123!')

        url = reverse('quizzes:take_quiz', kwargs={'quiz_id': self.paid_quiz.id})
        # Both questions answered correctly (100% >= 70%)
        post_data = {
            f'question_{self.q1.id}': self.c1_correct.id,
            f'question_{self.q2.id}': self.c2_correct.id,
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PASSED')
        self.assertContains(response, '100')

        # Check attempt created in DB
        attempt = QuizAttempt.objects.filter(student=self.student, quiz=self.paid_quiz).first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.total_questions, 2)
        self.assertEqual(attempt.correct_answers, 2)
        self.assertEqual(attempt.score_percent, 100.0)
        self.assertTrue(attempt.passed)
        self.assertIn('PASSED', str(attempt))

    def test_quiz_submission_failed(self):
        ContentUnlock.objects.create(user=self.student, content_item=self.paid_item, coins_spent=40)
        self.client.login(email='quizstudent@example.com', password='Password123!')

        url = reverse('quizzes:take_quiz', kwargs={'quiz_id': self.paid_quiz.id})
        # 1 correct out of 2 (50% < 70% threshold)
        post_data = {
            f'question_{self.q1.id}': self.c1_correct.id,
            f'question_{self.q2.id}': self.c2_wrong.id,
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'RETRY RECOMMENDED')
        self.assertContains(response, 'INCORRECT')
        self.assertContains(response, '50')

        attempt = QuizAttempt.objects.filter(student=self.student, quiz=self.paid_quiz).first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.correct_answers, 1)
        self.assertEqual(attempt.score_percent, 50.0)
        self.assertFalse(attempt.passed)
        self.assertIn('FAILED', str(attempt))
