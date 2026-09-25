import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from accounts.models import CustomUser
from content_hub.models import Subject, ContentItem, Curriculum
from wallet.models import StudentWallet, CoinTransaction, CoinBundle, PaymentMethod
from quizzes.models import Quiz, Question, Choice


def generate_simple_pdf(filepath, title="Rodz Tutoring Study Pack"):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    # A standard valid minimal 2-page PDF
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R /Resources << /Font << /F1 7 0 R >> >> >>
endobj
4 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 6 0 R /Resources << /Font << /F1 7 0 R >> >> >>
endobj
5 0 obj
<< /Length 140 >>
stream
BT
/F1 24 Tf
72 700 Td
(RODZ TUTORING - STUDY PACK) Tj
/F1 14 Tf
0 -40 Td
(Grade 12 Pure Mathematics - Examination Revision) Tj
0 -30 Td
(Protected In-App Document - Non-Downloadable) Tj
ET
endstream
endobj
6 0 obj
<< /Length 120 >>
stream
BT
/F1 18 Tf
72 700 Td
(Section 2: Worked Examples and Problem Sets) Tj
/F1 12 Tf
0 -40 Td
(Calculus, Functions and Analytical Geometry notes.) Tj
ET
endstream
endobj
7 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 8
0000000000 65535 f 
0000000010 00000 n 
0000000060 00000 n 
0000000125 00000 n 
0000000247 00000 n 
0000000369 00000 n 
0000000561 00000 n 
0000000733 00000 n 
trailer
<< /Size 8 /Root 1 0 R >>
startxref
806
%%EOF"""
    with open(filepath, 'wb') as f:
        f.write(pdf_content)


class Command(BaseCommand):
    help = 'Seeds initial subjects, demo users, study content, and quizzes'

    def handle(self, *args, **options):
        self.stdout.write("Seeding Rodz Tutoring database...")

        # 1. Subjects
        subjects_data = [
            {'name': 'Pure Mathematics', 'slug': 'pure-mathematics', 'icon_symbol': '√x', 'order': 1},
            {'name': 'Maths Literacy', 'slug': 'maths-literacy', 'icon_symbol': 'x+y', 'order': 2},
            {'name': 'Physical Sciences', 'slug': 'physical-sciences', 'icon_symbol': '⚛', 'order': 3},
            {'name': 'Accounting', 'slug': 'accounting', 'icon_symbol': '▣', 'order': 4},
            {'name': 'Economics', 'slug': 'economics', 'icon_symbol': '↗', 'order': 5},
            {'name': 'Business Studies', 'slug': 'business-studies', 'icon_symbol': '▱', 'order': 6},
            {'name': 'Cambridge O & A-Levels', 'slug': 'cambridge-curriculum', 'icon_symbol': '🎓', 'order': 7},
        ]

        subjects = {}
        for s in subjects_data:
            obj, _ = Subject.objects.get_or_create(slug=s['slug'], defaults=s)
            subjects[s['slug']] = obj
        self.stdout.write(self.style.SUCCESS(f"Created {len(subjects)} subjects."))

        # 1b. Curricula (Dynamic)
        curricula_data = [
            {'code': 'CAMBRIDGE', 'name': 'Cambridge Assessment International Education (CIE)', 'description': 'IGCSE, AS & A-Levels syllabus covering pure sciences and commercial subjects.', 'order': 1},
            {'code': 'CAPS', 'name': 'CAPS (Curriculum and Assessment Policy Statement)', 'description': 'South African National Senior Certificate curriculum for Grades 7 to 12.', 'order': 2},
            {'code': 'IEB', 'name': 'IEB (Independent Examinations Board)', 'description': 'South African independent schools curriculum with deep analytical problem solving.', 'order': 3},
        ]
        for c in curricula_data:
            Curriculum.objects.get_or_create(code=c['code'], defaults=c)
        self.stdout.write(self.style.SUCCESS("Created standard curricula (Cambridge, CAPS, IEB)."))

        # 1c. Coin Bundles
        bundles_data = [
            {'name': 'Starter Pack', 'price_zar': 60.00, 'coins': 60, 'badge': 'STARTER', 'description': 'Ideal for quick revision and quiz assessments', 'order': 1},
            {'name': 'Most Popular Pack', 'price_zar': 110.00, 'coins': 130, 'badge': '🔥 MOST POPULAR', 'description': 'Extra +10 bonus coins included for full exam revision', 'order': 2},
            {'name': 'Term Scholar Pack', 'price_zar': 220.00, 'coins': 280, 'badge': '⭐ BEST VALUE', 'description': 'Extra +30 bonus coins included for all subjects', 'order': 3},
            {'name': 'Mastery Year Pack', 'price_zar': 420.00, 'coins': 580, 'badge': '🏆 PRO SCHOLAR', 'description': 'Extra +80 bonus coins with full past papers & video access', 'order': 4},
        ]
        for b in bundles_data:
            CoinBundle.objects.get_or_create(name=b['name'], defaults=b)
        self.stdout.write(self.style.SUCCESS("Created coin bundles."))

        # 1d. Payment Methods / Accounts
        methods_data = [
            {
                'title': 'FNB Bank Transfer / EFT',
                'bank_name': 'First National Bank (FNB)',
                'account_number': '62891234567',
                'branch_code': '250655',
                'account_holder': 'Rodz Tutoring (Pty) Ltd',
                'account_type': 'Business Cheque',
                'reference_instructions': 'Use your student email or cell number as your deposit reference.',
                'additional_notes': 'Upload your bank receipt or notification screenshot below to activate coins.',
                'order': 1,
            },
            {
                'title': 'Capitec Pay / Instant EFT',
                'bank_name': 'Capitec Bank',
                'account_number': '1528994321',
                'branch_code': '470010',
                'account_holder': 'Rodz Tutoring (Pty) Ltd',
                'account_type': 'Savings / Business',
                'reference_instructions': 'Use your student email as reference.',
                'additional_notes': 'Instant verification within minutes during business hours.',
                'order': 2,
            },
        ]
        for m in methods_data:
            PaymentMethod.objects.get_or_create(title=m['title'], defaults=m)
        self.stdout.write(self.style.SUCCESS("Created payment methods."))

        # 2. Users (Admin, Tutor, Student)
        admin_user, created = CustomUser.objects.get_or_create(
            email='admin@rodztutoring.co.za',
            defaults={
                'full_name': 'Rodz Admin',
                'is_staff': True,
                'is_superuser': True,
                'is_admin_role': True,
                'is_tutor': True,
                'is_student': True,
                'grade': 'Grade 12',
                'curriculum': 'Combined',
            }
        )
        if created:
            admin_user.set_password('RodzAdmin2026!')
            admin_user.save()
            admin_wallet, _ = StudentWallet.objects.get_or_create(user=admin_user)
            admin_wallet.credit_coins(500, description="Admin initial setup balance")

        tutor_user, created = CustomUser.objects.get_or_create(
            email='tutor@rodztutoring.co.za',
            defaults={
                'full_name': 'Sarah Khumalo (Senior Tutor)',
                'is_tutor': True,
                'is_student': False,
                'grade': 'Grade 12',
                'curriculum': 'CAPS',
                'phone_number': '+27 74 568 5212',
            }
        )
        if created:
            tutor_user.set_password('RodzTutor2026!')
            tutor_user.save()

        student_user, created = CustomUser.objects.get_or_create(
            email='student@rodztutoring.co.za',
            defaults={
                'full_name': 'Lerato Dlamini',
                'is_student': True,
                'is_tutor': False,
                'grade': 'Grade 12',
                'curriculum': 'CAPS',
                'phone_number': '+27 82 123 4567',
            }
        )
        if created:
            student_user.set_password('RodzStudent2026!')
            student_user.save()
            student_wallet, _ = StudentWallet.objects.get_or_create(user=student_user)
            student_wallet.credit_coins(150, description="Welcome Bonus Pack")

        self.stdout.write(self.style.SUCCESS("Created demo accounts: admin, tutor, student."))

        # 3. Create Sample Protected PDF File
        demo_pdf_path = os.path.join(settings.MEDIA_ROOT, 'protected_pdfs', 'sample_study_pack.pdf')
        generate_simple_pdf(demo_pdf_path, "Grade 12 Pure Mathematics Study Pack")

        # 4. Content Items
        items_data = [
            {
                'title': 'Grade 12 Pure Mathematics Premium Study Pack',
                'slug': 'grade-12-pure-mathematics-premium-study-pack',
                'subject': subjects['pure-mathematics'],
                'grade': 'Grade 12',
                'curriculum': 'CAPS & IEB',
                'content_type': 'PDF',
                'category': 'Notes',
                'description': 'Complete examination revision pack covering Differential Calculus, Cubic Functions, Optimization, Analytical Geometry, and Trigonometry with full worked solutions.',
                'cover_svg_name': 'caps-g12-maths.svg',
                'is_free': False,
                'coin_price': 50,
                'pdf_file': 'protected_pdfs/sample_study_pack.pdf',
            },
            {
                'title': 'Grade 11 Mathematics Foundations & Algebra',
                'slug': 'grade-11-mathematics-foundations-algebra',
                'subject': subjects['pure-mathematics'],
                'grade': 'Grade 11',
                'curriculum': 'CAPS & IEB',
                'content_type': 'PDF',
                'category': 'Notes',
                'description': 'Master quadratic equations, inequalities, exponents, and number patterns with step-by-step exam techniques.',
                'cover_svg_name': 'caps-g11-maths.svg',
                'is_free': False,
                'coin_price': 40,
                'pdf_file': 'protected_pdfs/sample_study_pack.pdf',
            },
            {
                'title': 'Grade 12 Accounting Comprehensive Exam Pack',
                'slug': 'grade-12-accounting-comprehensive-exam-pack',
                'subject': subjects['accounting'],
                'grade': 'Grade 12',
                'curriculum': 'CAPS & IEB',
                'content_type': 'PDF',
                'category': 'Past Papers',
                'description': 'Companies Financial Statements, Balance Sheets, Cash Flow Analysis, Fixed Assets, and Inventory Valuations.',
                'cover_svg_name': 'caps-accounting.svg',
                'is_free': False,
                'coin_price': 50,
                'pdf_file': 'protected_pdfs/sample_study_pack.pdf',
            },
            {
                'title': 'Grade 12 Physical Sciences - Work, Energy & Power Breakdown',
                'slug': 'grade-12-physics-work-energy-power',
                'subject': subjects['physical-sciences'],
                'grade': 'Grade 12',
                'curriculum': 'CAPS & IEB',
                'content_type': 'VIDEO',
                'category': 'Video Lessons',
                'description': 'Deep dive video lesson breaking down Newton’s Laws, conservation of mechanical energy, and exam question walkthroughs.',
                'cover_svg_name': 'caps-physics.svg',
                'is_free': False,
                'coin_price': 30,
                'youtube_url': 'https://www.youtube.com/watch?v=2WS1dQ9-Bl8',
            },
            {
                'title': 'Grade 12 Mathematics - Calculus Derivatives & Tangents Masterclass',
                'slug': 'grade-12-maths-calculus-derivatives-video',
                'subject': subjects['pure-mathematics'],
                'grade': 'Grade 12',
                'curriculum': 'CAPS & IEB',
                'content_type': 'VIDEO',
                'category': 'Video Lessons',
                'description': 'Master first-principles differentiation, the power rule, cubic tangents, and optimization with real exam questions.',
                'cover_svg_name': 'caps-g12-maths.svg',
                'is_free': True,
                'coin_price': 0,
                'youtube_url': 'https://www.youtube.com/watch?v=9vKqVkMQHKk',
            },
            {
                'title': 'Grade 10 Mathematics Essential Formulae & Notes',
                'slug': 'grade-10-mathematics-essential-notes',
                'subject': subjects['pure-mathematics'],
                'grade': 'Grade 10',
                'curriculum': 'CAPS & IEB',
                'content_type': 'PDF',
                'category': 'Notes',
                'description': 'Free introductory starter pack for Grade 10 learners revising factorization, algebraic fractions, and linear equations.',
                'cover_svg_name': 'caps-g10-maths.svg',
                'is_free': True,
                'coin_price': 0,
                'pdf_file': 'protected_pdfs/sample_study_pack.pdf',
            },
            {
                'title': 'Grade 12 Pure Mathematics - Calculus & Functions Assessment Quiz',
                'slug': 'grade-12-pure-maths-calculus-quiz',
                'subject': subjects['pure-mathematics'],
                'grade': 'Grade 12',
                'curriculum': 'CAPS & IEB',
                'content_type': 'QUIZ',
                'category': 'Quiz',
                'description': 'Interactive 4-question timed assessment testing differentiation, stationary points, and curve sketching.',
                'cover_svg_name': 'caps-exam.svg',
                'is_free': False,
                'coin_price': 20,
            },
        ]

        for item in items_data:
            c_item, _ = ContentItem.objects.get_or_create(slug=item['slug'], defaults=item)
            
            # If this item is the quiz, create the Quiz and Questions
            if item['content_type'] == 'QUIZ':
                quiz, _ = Quiz.objects.get_or_create(
                    content_item=c_item,
                    defaults={
                        'title': item['title'],
                        'instructions': 'You have 10 minutes. Select the correct option for each calculus question.',
                        'time_limit_minutes': 10,
                        'pass_percentage': 70,
                    }
                )

                if quiz.questions.count() == 0:
                    # Q1
                    q1 = Question.objects.create(
                        quiz=quiz,
                        text="What is the derivative f'(x) of f(x) = 3x^3 - 5x + 7 with respect to x?",
                        explanation="Using the power rule d/dx(ax^n) = a*n*x^(n-1): d/dx(3x^3) = 9x^2, d/dx(-5x) = -5, d/dx(7) = 0. Thus f'(x) = 9x^2 - 5.",
                        order=0
                    )
                    Choice.objects.create(question=q1, text="9x^2 - 5", is_correct=True)
                    Choice.objects.create(question=q1, text="9x^3 - 5x", is_correct=False)
                    Choice.objects.create(question=q1, text="6x^2 - 5", is_correct=False)
                    Choice.objects.create(question=q1, text="3x^2 - 5", is_correct=False)

                    # Q2
                    q2 = Question.objects.create(
                        quiz=quiz,
                        text="At the stationary points of a smooth function y = f(x), what is the value of f'(x)?",
                        explanation="A stationary point occurs where the gradient tangent of the curve is horizontal, meaning f'(x) = 0.",
                        order=1
                    )
                    Choice.objects.create(question=q2, text="f'(x) = 0", is_correct=True)
                    Choice.objects.create(question=q2, text="f'(x) > 0", is_correct=False)
                    Choice.objects.create(question=q2, text="f'(x) = 1", is_correct=False)
                    Choice.objects.create(question=q2, text="f'(x) < 0", is_correct=False)

                    # Q3
                    q3 = Question.objects.create(
                        quiz=quiz,
                        text="If f''(x) > 0 on an interval, what can be deduced about the concavity of f(x)?",
                        explanation="When the second derivative f''(x) is positive, the function is concave up (holds water like a smile).",
                        order=2
                    )
                    Choice.objects.create(question=q3, text="Concave upwards", is_correct=True)
                    Choice.objects.create(question=q3, text="Concave downwards", is_correct=False)
                    Choice.objects.create(question=q3, text="Linear and horizontal", is_correct=False)
                    Choice.objects.create(question=q3, text="Undefined inflection", is_correct=False)

                    # Q4
                    q4 = Question.objects.create(
                        quiz=quiz,
                        text="Find the coordinates of the y-intercept of the cubic function f(x) = 2x^3 - 4x^2 + x - 8.",
                        explanation="The y-intercept occurs where x = 0. Substituting x = 0: f(0) = 2(0)^3 - 4(0)^2 + 0 - 8 = -8. Thus (0, -8).",
                        order=3
                    )
                    Choice.objects.create(question=q4, text="(0, -8)", is_correct=True)
                    Choice.objects.create(question=q4, text="(0, 8)", is_correct=False)
                    Choice.objects.create(question=q4, text="(-8, 0)", is_correct=False)
                    Choice.objects.create(question=q4, text="(2, -8)", is_correct=False)

        self.stdout.write(self.style.SUCCESS("Seeding complete! Database is primed and ready."))
