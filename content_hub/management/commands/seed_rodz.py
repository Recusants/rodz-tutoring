import os
from decimal import Decimal
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from accounts.models import CustomUser
from content_hub.models import (
    AboutContent,
    ContactInfo,
    ContentItem,
    Course,
    Curriculum,
    HowToGuide,
    HowToStep,
    Subject,
    TermsContent,
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


def generate_simple_pdf(filepath, heading="RODZ TUTORING - STUDY PACK", subtitle="Protected In-App Study Resource"):
    """Create a valid minimal 2-page PDF file on disk if missing."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if os.path.exists(filepath):
        return
    clean_h = heading[:60].replace("(", "").replace(")", "")
    clean_s = subtitle[:60].replace("(", "").replace(")", "")
    pdf_content = f"""%PDF-1.4
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
<< /Length 160 >>
stream
BT
/F1 20 Tf
72 700 Td
({clean_h}) Tj
/F1 13 Tf
0 -40 Td
({clean_s}) Tj
0 -30 Td
(Protected In-App Document - Rodz Tutoring) Tj
ET
endstream
endobj
6 0 obj
<< /Length 120 >>
stream
BT
/F1 16 Tf
72 700 Td
(Section 2: Worked Examples and Exam Revision) Tj
/F1 12 Tf
0 -35 Td
(Structured step-by-step practice sets.) Tj
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
0000000581 00000 n 
0000000753 00000 n 
trailer
<< /Size 8 /Root 1 0 R >>
startxref
826
%%EOF""".encode("latin-1", errors="ignore")
    with open(filepath, "wb") as f:
        f.write(pdf_content)


def generate_avatar_png(filepath, bg_color=(30, 64, 175)):
    """Create a clean placeholder avatar PNG using Pillow if missing."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if os.path.exists(filepath):
        return
    img = Image.new("RGB", (200, 200), bg_color)
    draw = ImageDraw.Draw(img)
    draw.ellipse((55, 35, 145, 125), fill=(241, 245, 249))
    draw.ellipse((35, 130, 165, 220), fill=(241, 245, 249))
    img.save(filepath, "PNG")


class Command(BaseCommand):
    help = "Idempotently seeds 10-20 objects across all models and accounts for every user type."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seeding Rodz Tutoring database (full idempotent dataset)...")

        self._seed_media_assets()
        curricula = self._seed_curricula()
        subjects = self._seed_subjects()
        users = self._seed_users()
        system_wallet = self._seed_system_wallet()
        self._seed_site_singletons()
        guides = self._seed_how_to_guides()
        self._seed_how_to_steps(guides)

        bundles = self._seed_coin_bundles()
        methods = self._seed_payment_methods()
        items = self._seed_content_items(subjects, curricula)
        courses = self._seed_courses(users, subjects, curricula, items)
        quizzes = self._seed_quizzes(items)
        self._seed_quiz_attempts(users, quizzes)
        self._seed_wallet_activity(users, system_wallet, bundles, methods, items, courses)

        self.stdout.write(self.style.SUCCESS("Seeding complete! All models and user types are primed."))

    def _seed_media_assets(self):
        generate_simple_pdf(
            os.path.join(settings.MEDIA_ROOT, "protected_pdfs", "sample_study_pack.pdf"),
            "RODZ TUTORING - STUDY PACK",
            "Examination Revision & Worked Solutions",
        )
        generate_simple_pdf(
            os.path.join(settings.MEDIA_ROOT, "protected_pdfs", "past_paper_pack.pdf"),
            "RODZ TUTORING - PAST PAPER PACK",
            "Full Memorandum & Examiner Notes",
        )
        generate_simple_pdf(
            os.path.join(settings.MEDIA_ROOT, "payment_proofs", "seed_pop_receipt.pdf"),
            "BANK EFT PAYMENT RECEIPT",
            "Verified Deposit Proof of Payment",
        )
        colors = [(30, 64, 175), (15, 118, 110), (126, 34, 206), (180, 83, 9)]
        for idx, color in enumerate(colors, start=1):
            generate_avatar_png(
                os.path.join(settings.MEDIA_ROOT, "tutor_profiles", f"seed_tutor_{idx}.png"),
                bg_color=color,
            )

    def _seed_curricula(self):
        curricula_data = [
            ("CAMBRIDGE", "Cambridge Assessment International Education (CIE)", "IGCSE, AS & A-Levels syllabus covering pure sciences and commercial subjects.", 1),
            ("CAPS", "CAPS (Curriculum and Assessment Policy Statement)", "South African National Senior Certificate curriculum for Grades 7 to 12.", 2),
            ("IEB", "IEB (Independent Examinations Board)", "South African independent schools curriculum with deep analytical problem solving.", 3),
            ("CAMBRIDGE-IGCSE", "Cambridge IGCSE", "International General Certificate of Secondary Education (Grades 9-10).", 4),
            ("CAMBRIDGE-AS", "Cambridge AS-Level", "Cambridge International Advanced Subsidiary Level (Grade 11).", 5),
            ("CAMBRIDGE-A", "Cambridge A-Level", "Cambridge International Advanced Level (Grade 12).", 6),
            ("CAMBRIDGE-O", "Cambridge O-Level", "Cambridge Ordinary Level international qualification.", 7),
            ("IB-DP", "IB Diploma Programme", "International Baccalaureate Diploma Programme for senior secondary.", 8),
            ("IB-MYP", "IB Middle Years Programme", "International Baccalaureate Middle Years Programme (Grades 7-10).", 9),
            ("SACAI", "SACAI National Senior Certificate", "South African Comprehensive Assessment Institute NSC curriculum.", 10),
            ("EDEXCEL", "Pearson Edexcel IGCSE", "Edexcel International GCSE STEM & commerce pathway.", 11),
            ("ZIMSEC", "ZIMSEC O & A-Level", "Zimbabwe School Examinations Council O & A-Level syllabus.", 12),
        ]
        result = {}
        for code, name, desc, order in curricula_data:
            obj, _ = Curriculum.objects.get_or_create(
                code=code,
                defaults={"name": name, "description": desc, "order": order, "is_active": True},
            )
            result[code] = obj
        return result

    def _seed_subjects(self):
        subjects_data = [
            ("pure-mathematics", "Pure Mathematics", "√x", "Algebra, calculus, trigonometry, analytical & Euclidean geometry.", 1),
            ("maths-literacy", "Maths Literacy", "x+y", "Finance, measurement, maps, plans, and practical data handling.", 2),
            ("physical-sciences", "Physical Sciences", "⚛", "Mechanics, waves, electricity, magnetism, and chemical change.", 3),
            ("accounting", "Accounting", "▣", "Financial statements, cash flows, reconciliations, and cost accounting.", 4),
            ("economics", "Economics", "↗", "Microeconomics, macroeconomics, inflation, and trade policy.", 5),
            ("business-studies", "Business Studies", "▱", "Business environments, ventures, management, and ethics.", 6),
            ("cambridge-curriculum", "Cambridge O & A-Levels", "🎓", "Combined Cambridge international exam prep across core subjects.", 7),
            ("chemistry", "Chemistry", "⚗", "Stoichiometry, organic chemistry, equilibrium, and electrochemistry.", 8),
            ("physics", "Physics", "⚡", "Kinematics, dynamics, fields, nuclear & quantum physics.", 9),
            ("life-sciences", "Life Sciences", "🧬", "Genetics, cellular respiration, evolution, and human physiology.", 10),
            ("english-hl", "English Home Language", "✍", "Literature essays, comprehension, grammar, and visual literacy.", 11),
            ("information-technology", "Information Technology", "💻", "Algorithms, OOP, SQL databases, and systems architecture.", 12),
            ("cat", "Computer Applications Tech", "⌨", "Spreadsheets, word processing, databases, and HTML.", 13),
            ("geography", "Geography", "🌍", "Climatology, geomorphology, settlement, and GIS mapwork.", 14),
        ]
        result = {}
        for slug, name, icon, desc, order in subjects_data:
            obj, _ = Subject.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "icon_symbol": icon, "description": desc, "order": order},
            )
            result[slug] = obj
        return result

    def _seed_users(self):
        now = timezone.now()
        users_spec = [
            # 1-2: Superuser Full Admins (Admin + Tutor + Student)
            {
                "key": "admin",
                "email": "admin@rodztutoring.co.za",
                "password": "RodzAdmin2026!",
                "full_name": "Rodz Admin",
                "phone": "+27 74 568 5212",
                "grade": "Grade 12",
                "curriculum": "Combined",
                "is_staff": True,
                "is_superuser": True,
                "is_admin_role": True,
                "is_tutor": True,
                "is_student": True,
                "tutor_status": "APPROVED",
                "bio": "Platform Administrator & Lead Mathematics Specialist.",
                "pic": "tutor_profiles/seed_tutor_1.png",
                "initial_coins": 500,
            },
            {
                "key": "director",
                "email": "director@rodztutoring.co.za",
                "password": "RodzAdmin2026!",
                "full_name": "Thabo Mokoena (Academic Director)",
                "phone": "+27 71 200 1001",
                "grade": "Alumni/Other",
                "curriculum": "Combined",
                "is_staff": True,
                "is_superuser": True,
                "is_admin_role": True,
                "is_tutor": True,
                "is_student": True,
                "tutor_status": "APPROVED",
                "bio": "Academic Director overseeing curriculum alignment across CAPS, IEB, and Cambridge.",
                "pic": "tutor_profiles/seed_tutor_2.png",
                "initial_coins": 400,
            },
            # 3-4: Staff-Only Admins (is_admin_role=True, is_tutor=False, is_student=False)
            {
                "key": "ops_admin",
                "email": "operations@rodztutoring.co.za",
                "password": "RodzAdmin2026!",
                "full_name": "Nomsa Dube (Operations Admin)",
                "phone": "+27 71 200 1002",
                "grade": "Alumni/Other",
                "curriculum": "CAPS",
                "is_staff": True,
                "is_superuser": False,
                "is_admin_role": True,
                "is_tutor": False,
                "is_student": False,
                "tutor_status": "NONE",
                "initial_coins": 100,
            },
            {
                "key": "fin_admin",
                "email": "finance@rodztutoring.co.za",
                "password": "RodzAdmin2026!",
                "full_name": "Kagiso Molefe (Finance Admin)",
                "phone": "+27 71 200 1003",
                "grade": "Alumni/Other",
                "curriculum": "IEB",
                "is_staff": True,
                "is_superuser": False,
                "is_admin_role": True,
                "is_tutor": False,
                "is_student": False,
                "tutor_status": "NONE",
                "initial_coins": 100,
            },
            # 5-8: Approved Pure Tutors
            {
                "key": "tutor",
                "email": "tutor@rodztutoring.co.za",
                "password": "RodzTutor2026!",
                "full_name": "Sarah Khumalo (Senior Tutor)",
                "phone": "+27 74 568 5212",
                "grade": "Grade 12",
                "curriculum": "CAPS",
                "is_tutor": True,
                "is_student": False,
                "tutor_status": "APPROVED",
                "bio": "BSc Honours Mathematics. 8+ years preparing Matric & IEB distinction candidates.",
                "pic": "tutor_profiles/seed_tutor_1.png",
                "initial_coins": 250,
            },
            {
                "key": "tutor_physics",
                "email": "tutor.physics@rodztutoring.co.za",
                "password": "RodzTutor2026!",
                "full_name": "David van der Merwe (Physics Tutor)",
                "phone": "+27 82 310 4401",
                "grade": "Grade 12",
                "curriculum": "IEB",
                "is_tutor": True,
                "is_student": False,
                "tutor_status": "APPROVED",
                "bio": "Physical Sciences & Chemistry specialist for Grades 10-12 CAPS and IEB.",
                "pic": "tutor_profiles/seed_tutor_2.png",
                "initial_coins": 220,
            },
            {
                "key": "tutor_accounting",
                "email": "tutor.accounting@rodztutoring.co.za",
                "password": "RodzTutor2026!",
                "full_name": "Priya Naidoo (Accounting & Economics Tutor)",
                "phone": "+27 83 412 8890",
                "grade": "Grade 12",
                "curriculum": "CAPS",
                "is_tutor": True,
                "is_student": False,
                "tutor_status": "APPROVED",
                "bio": "CA(SA) academic coach focusing on Financial Accounting, Cash Flows, and Economics.",
                "pic": "tutor_profiles/seed_tutor_3.png",
                "initial_coins": 200,
            },
            {
                "key": "tutor_cambridge",
                "email": "tutor.cambridge@rodztutoring.co.za",
                "password": "RodzTutor2026!",
                "full_name": "Dr. Samuel Chibanda (Cambridge Specialist)",
                "phone": "+27 84 550 1122",
                "grade": "Grade 12",
                "curriculum": "Cambridge",
                "is_tutor": True,
                "is_student": False,
                "tutor_status": "APPROVED",
                "bio": "Cambridge IGCSE, AS & A-Level Mathematics and Physics examiner mentor.",
                "pic": "tutor_profiles/seed_tutor_4.png",
                "initial_coins": 300,
            },
            # 9-10: Dual-Role Approved Tutor + Student
            {
                "key": "peer_tutor1",
                "email": "peer.tutor1@rodztutoring.co.za",
                "password": "RodzTutor2026!",
                "full_name": "Aisha Patel (Tutor & Uni Prep Student)",
                "phone": "+27 72 601 3344",
                "grade": "Alumni/Other",
                "curriculum": "IEB",
                "is_tutor": True,
                "is_student": True,
                "tutor_status": "APPROVED",
                "bio": "Engineering student tutoring Grade 8-11 Pure Maths and Physical Sciences.",
                "pic": "tutor_profiles/seed_tutor_3.png",
                "initial_coins": 180,
            },
            {
                "key": "peer_tutor2",
                "email": "peer.tutor2@rodztutoring.co.za",
                "password": "RodzTutor2026!",
                "full_name": "Luyanda Nkosi (Tutor & Honours Student)",
                "phone": "+27 73 712 9901",
                "grade": "Alumni/Other",
                "curriculum": "CAPS",
                "is_tutor": True,
                "is_student": True,
                "tutor_status": "APPROVED",
                "bio": "BCom Honours mentor assisting learners with Accounting & Business Studies.",
                "pic": "tutor_profiles/seed_tutor_4.png",
                "initial_coins": 160,
            },
            # 11-12: Pending Tutor Applicants (is_student=True, is_tutor=False, tutor_status='PENDING')
            {
                "key": "pending1",
                "email": "applicant.pending1@rodztutoring.co.za",
                "password": "RodzStudent2026!",
                "full_name": "Sipho Zungu (Pending Tutor)",
                "phone": "+27 76 111 2233",
                "grade": "Alumni/Other",
                "curriculum": "CAPS",
                "is_tutor": False,
                "is_student": True,
                "tutor_status": "PENDING",
                "tutor_applied_at": now,
                "bio": "BEd Mathematics graduate applying to teach Grade 10-12 Pure Maths & Maths Lit.",
                "pic": "tutor_profiles/seed_tutor_1.png",
                "initial_coins": 80,
            },
            {
                "key": "pending2",
                "email": "applicant.pending2@rodztutoring.co.za",
                "password": "RodzStudent2026!",
                "full_name": "Claire Botha (Pending Tutor)",
                "phone": "+27 78 222 3344",
                "grade": "Alumni/Other",
                "curriculum": "Cambridge",
                "is_tutor": False,
                "is_student": True,
                "tutor_status": "PENDING",
                "tutor_applied_at": now,
                "bio": "Cambridge Biology and Chemistry specialist with 4 years of online tutoring.",
                "pic": "tutor_profiles/seed_tutor_2.png",
                "initial_coins": 90,
            },
            # 13-14: Rejected Tutor Applicants (is_student=True, is_tutor=False, tutor_status='REJECTED')
            {
                "key": "rejected1",
                "email": "applicant.rejected1@rodztutoring.co.za",
                "password": "RodzStudent2026!",
                "full_name": "Jason Petersen (Rejected Applicant)",
                "phone": "+27 79 333 4455",
                "grade": "Alumni/Other",
                "curriculum": "CAPS",
                "is_tutor": False,
                "is_student": True,
                "tutor_status": "REJECTED",
                "tutor_applied_at": now,
                "tutor_rejection_reason": "Please upload certified academic transcripts and sample lesson notes.",
                "bio": "Applied to tutor Grade 9-10 Mathematics.",
                "initial_coins": 60,
            },
            {
                "key": "rejected2",
                "email": "applicant.rejected2@rodztutoring.co.za",
                "password": "RodzStudent2026!",
                "full_name": "Mpho Sithole (Rejected Applicant)",
                "phone": "+27 81 444 5566",
                "grade": "Alumni/Other",
                "curriculum": "IEB",
                "is_tutor": False,
                "is_student": True,
                "tutor_status": "REJECTED",
                "tutor_applied_at": now,
                "tutor_rejection_reason": "Incomplete subject specialization details; eligible to re-apply after update.",
                "bio": "Applied to tutor Economics and Geography.",
                "initial_coins": 50,
            },
            # 15-20: Pure Students across Grades 7-12 and Curricula
            {
                "key": "student",
                "email": "student@rodztutoring.co.za",
                "password": "RodzStudent2026!",
                "full_name": "Lerato Dlamini",
                "phone": "+27 82 123 4567",
                "grade": "Grade 12",
                "curriculum": "CAPS",
                "is_tutor": False,
                "is_student": True,
                "tutor_status": "NONE",
                "initial_coins": 300,
            },
            {
                "key": "student_g7",
                "email": "student.g7@rodztutoring.co.za",
                "password": "RodzStudent2026!",
                "full_name": "Ethan Jacobs",
                "phone": "+27 82 501 0007",
                "grade": "Grade 7",
                "curriculum": "CAPS",
                "is_tutor": False,
                "is_student": True,
                "tutor_status": "NONE",
                "initial_coins": 120,
            },
            {
                "key": "student_g8",
                "email": "student.g8@rodztutoring.co.za",
                "password": "RodzStudent2026!",
                "full_name": "Zanele Mthembu",
                "phone": "+27 82 501 0008",
                "grade": "Grade 8",
                "curriculum": "IEB",
                "is_tutor": False,
                "is_student": True,
                "tutor_status": "NONE",
                "initial_coins": 150,
            },
            {
                "key": "student_g9",
                "email": "student.g9@rodztutoring.co.za",
                "password": "RodzStudent2026!",
                "full_name": "Liam Pillay",
                "phone": "+27 82 501 0009",
                "grade": "Grade 9",
                "curriculum": "Cambridge",
                "is_tutor": False,
                "is_student": True,
                "tutor_status": "NONE",
                "initial_coins": 180,
            },
            {
                "key": "student_g10",
                "email": "student.g10@rodztutoring.co.za",
                "password": "RodzStudent2026!",
                "full_name": "Amahle Ndlovu",
                "phone": "+27 82 501 0010",
                "grade": "Grade 10",
                "curriculum": "CAPS",
                "is_tutor": False,
                "is_student": True,
                "tutor_status": "NONE",
                "initial_coins": 200,
            },
            {
                "key": "student_g11",
                "email": "student.g11@rodztutoring.co.za",
                "password": "RodzStudent2026!",
                "full_name": "Tadiwa Moyo",
                "phone": "+27 82 501 0011",
                "grade": "Grade 11",
                "curriculum": "Cambridge",
                "is_tutor": False,
                "is_student": True,
                "tutor_status": "NONE",
                "initial_coins": 240,
            },
        ]

        result = {}
        admin_ref = None
        for spec in users_spec:
            defaults = {
                "full_name": spec["full_name"],
                "phone_number": spec["phone"],
                "grade": spec["grade"],
                "curriculum": spec["curriculum"],
                "is_staff": spec.get("is_staff", False),
                "is_superuser": spec.get("is_superuser", False),
                "is_admin_role": spec.get("is_admin_role", False),
                "is_tutor": spec.get("is_tutor", False),
                "is_student": spec.get("is_student", True),
                "tutor_status": spec.get("tutor_status", "NONE"),
                "bio": spec.get("bio", ""),
                "profile_picture": spec.get("pic", ""),
                "tutor_applied_at": spec.get("tutor_applied_at"),
                "tutor_approved_at": now if spec.get("tutor_status") == "APPROVED" else None,
                "tutor_rejection_reason": spec.get("tutor_rejection_reason", ""),
                "tutor_reviewed_by": admin_ref if spec.get("tutor_status") in ("APPROVED", "REJECTED") else None,
            }
            user, created = CustomUser.objects.get_or_create(email=spec["email"], defaults=defaults)
            if created:
                user.set_password(spec["password"])
                user.save()
                wallet, _ = StudentWallet.objects.get_or_create(user=user)
                if spec["initial_coins"] > 0:
                    wallet.credit_coins(
                        spec["initial_coins"],
                        description=f"Seed initial setup balance ({spec['key']})",
                        admin_user=admin_ref,
                        transaction_type="BONUS",
                    )
            if spec["key"] == "admin":
                admin_ref = user
            result[spec["key"]] = user
        return result

    def _seed_system_wallet(self):
        return SystemWallet.get_instance()

    def _seed_site_singletons(self):
        AboutContent.get_solo()
        ContactInfo.get_solo()
        TermsContent.get_solo()

    def _seed_how_to_guides(self):
        guides_data = [
            ("how-it-works", "How Rodz Tutoring Works", "STUDENT ONBOARDING GUIDE", "Step-by-step guide to enrolling, buying coins, unlocking resources, and acing exams.", 1),
            ("how-to-buy-coins", "How to Buy & Top Up Study Coins", "COIN WALLET GUIDE", "Purchase coin bundles via EFT/Instant EFT and upload proof of payment.", 2),
            ("how-to-apply-tutor", "How to Become a Verified Rodz Tutor", "TUTOR ONBOARDING", "Submit your qualifications and bio to publish courses and earn study coins.", 3),
            ("how-to-create-courses", "How to Build & Publish Course Bundles", "CREATOR GUIDE", "Group PDFs, video walkthroughs, and quizzes into discounted course bundles.", 4),
            ("how-to-take-quizzes", "How Interactive Timed Quizzes Work", "ASSESSMENT GUIDE", "Complete timed multiple-choice quizzes with instant worked explanations.", 5),
            ("how-to-transfer-coins", "How Peer-to-Peer Coin Transfers Work", "P2P TRANSFER GUIDE", "Send coins directly to classmates or study partners with transparent fees.", 6),
            ("how-to-cash-out-coins", "Tutor Coin Redemption & Cash-Out Guide", "PAYOUT GUIDE", "Redeem earned study coins at the prevailing platform cash-out rate.", 7),
            ("protected-viewer-guide", "Using the Non-Downloadable Study Viewer", "SECURITY & VIEWER", "Navigate multi-page canvas PDFs and embedded lessons safely on any device.", 8),
            ("exam-revision-strategy", "Matric & A-Level Exam Prep Roadmap", "STUDY STRATEGY", "Use past papers, video solutions, and diagnostic quizzes effectively.", 9),
            ("parent-portal-overview", "Parent & Guardian Monitoring Guide", "PARENT GUIDE", "Track learner coin activity, unlocked bundles, and quiz performance.", 10),
        ]
        result = {}
        for slug, title, badge, subtitle, order in guides_data:
            obj, _ = HowToGuide.objects.get_or_create(
                slug=slug,
                defaults={
                    "title": title,
                    "badge_text": badge,
                    "subtitle": subtitle,
                    "is_active": True,
                    "order": order,
                },
            )
            result[slug] = obj
        return result

    def _seed_how_to_steps(self, guides):
        steps_data = [
            ("how-it-works", 1, "STEP 1", "Create Your Free Learner Account", "fa-solid fa-user-plus", "Register using your email, select your grade (7-12) and curriculum (CAPS, IEB, or Cambridge).", "Enrol Free", "/accounts/register/", 1),
            ("how-it-works", 2, "STEP 2", "Browse Free & Premium Resources", "fa-solid fa-book-open", "Explore filtered PDF study packs, video masterclasses, past papers, and timed quizzes.", "Browse Catalog", "/content/", 2),
            ("how-it-works", 3, "STEP 3", "Top Up Your Study Coin Wallet", "fa-solid fa-coins", "Select a coin bundle, pay via bank EFT, and upload proof of payment for quick crediting.", "Buy Coins", "/wallet/buy-coins/", 3),
            ("how-it-works", 4, "STEP 4", "Unlock Packs or Full Course Bundles", "fa-solid fa-unlock-keyhole", "Spend coins once for academic-year access; previously unlocked items discount course bundles automatically.", "View Wallet", "/wallet/history/", 4),
            ("how-it-works", 5, "STEP 5", "Attempt Timed Assessment Quizzes", "fa-solid fa-list-check", "Test your mastery under exam timing and review step-by-step worked explanations.", "Dashboard", "/accounts/dashboard/", 5),
            ("how-it-works", 6, "STEP 6", "Track Scores & Connect With Tutors", "fa-solid fa-graduation-cap", "Monitor pass percentages and book focused live support with vetted subject specialists.", "Meet Tutors", "/content/tutoring/", 6),
            ("how-to-buy-coins", 1, "STEP 1", "Choose a Coin Bundle", "fa-solid fa-gem", "Compare starter and value scholar packs on the Buy Coins page.", "Buy Coins", "/wallet/buy-coins/", 1),
            ("how-to-buy-coins", 2, "STEP 2", "Make an EFT Deposit & Upload POP", "fa-solid fa-receipt", "Deposit using your email reference and upload the receipt screenshot for admin approval.", "Upload POP", "/wallet/buy-coins/", 2),
            ("how-to-apply-tutor", 1, "STEP 1", "Submit Your Tutor Application", "fa-solid fa-chalkboard-user", "Upload your profile picture and detail your subjects and teaching credentials.", "Apply Now", "/accounts/tutor/apply/", 1),
            ("how-to-apply-tutor", 2, "STEP 2", "Admin Review & Activation", "fa-solid fa-circle-check", "Once approved by administration, switch to Tutor Mode from your top navigation bar.", "Dashboard", "/accounts/dashboard/", 2),
            ("how-to-create-courses", 1, "STEP 1", "Upload Individual Study Items", "fa-solid fa-cloud-arrow-up", "Add PDF notes, YouTube video walkthroughs, or quizzes to the content hub.", "Upload Resource", "/content/upload/", 1),
            ("how-to-create-courses", 2, "STEP 2", "Assemble & Submit Course Bundle", "fa-solid fa-boxes-stacked", "Group items into a discounted bundle and submit for quick admin approval.", "Create Course", "/content/courses/create/", 2),
            ("how-to-take-quizzes", 1, "STEP 1", "Launch Timed Assessment", "fa-solid fa-stopwatch", "Read quiz instructions and track the countdown timer while answering questions.", "Catalog", "/content/", 1),
            ("how-to-transfer-coins", 1, "STEP 1", "Send Coins to Any Peer", "fa-solid fa-paper-plane", "Enter recipient email and amount; a transparent fee routes to the system treasury.", "Transfer Coins", "/wallet/transfer/", 1),
            ("how-to-cash-out-coins", 1, "STEP 1", "Redeem Earned Tutor Coins", "fa-solid fa-money-bill-transfer", "Convert eligible wallet coins at the live cash-out rate once above the minimum threshold.", "Sell Coins", "/wallet/sell/", 1),
            ("protected-viewer-guide", 1, "STEP 1", "View Watermarked Canvas Pages", "fa-solid fa-shield-halved", "Protected documents render crisply inside your browser with personalized licensing watermarks.", "Terms", "/content/terms/", 1),
        ]
        for guide_slug, num, badge, title, icon, desc, cta_txt, cta_url, order in steps_data:
            HowToStep.objects.get_or_create(
                guide=guides[guide_slug],
                step_number=num,
                defaults={
                    "badge": badge,
                    "title": title,
                    "icon_class": icon,
                    "description": desc,
                    "call_to_action_text": cta_txt,
                    "call_to_action_url": cta_url,
                    "order": order,
                },
            )

    def _seed_coin_bundles(self):
        bundles_data = [
            ("Starter Pack", 60, Decimal("60.00"), "STARTER", "Ideal for quick revision and single quiz assessments", 1),
            ("Most Popular Pack", 130, Decimal("110.00"), "🔥 MOST POPULAR", "Extra +20 bonus value for full exam revision", 2),
            ("Term Scholar Pack", 280, Decimal("220.00"), "⭐ BEST VALUE", "Extra bonus coins included for multi-subject prep", 3),
            ("Mastery Year Pack", 580, Decimal("420.00"), "🏆 PRO SCHOLAR", "Full academic year bundle across past papers & videos", 4),
            ("Weekend Cram Pack", 90, Decimal("85.00"), "⚡ CRAM", "Focused weekend past-paper sprint pack", 5),
            ("Exam Blitz Pack", 200, Decimal("165.00"), "🎯 EXAM BLITZ", "Unlock 4 full course packs before finals", 6),
            ("Study Group Pack", 350, Decimal("275.00"), "👥 GROUP", "Extra coins suitable for peer sharing & study groups", 7),
            ("Cambridge A-Level Pack", 450, Decimal("340.00"), "🎓 CAMBRIDGE", "Tailored for AS & A-Level intensive courses", 8),
            ("Olympiad Prep Pack", 160, Decimal("135.00"), "🧠 OLYMPIAD", "Advanced problem-solving sets and worked memos", 9),
            ("Holiday Bootcamp Pack", 750, Decimal("520.00"), "🚀 BOOTCAMP", "Maximum coin reserve with lowest per-coin rate", 10),
        ]
        result = {}
        for name, coins, price, badge, desc, order in bundles_data:
            obj, _ = CoinBundle.objects.get_or_create(
                name=name,
                defaults={
                    "coins": coins,
                    "price_zar": price,
                    "badge": badge,
                    "description": desc,
                    "is_active": True,
                    "order": order,
                },
            )
            result[name] = obj
        return result

    def _seed_payment_methods(self):
        methods_data = [
            ("FNB Bank Transfer / EFT", "First National Bank (FNB)", "62891234567", "250655", "Business Cheque", 1, True),
            ("Capitec Pay / Instant EFT", "Capitec Bank", "1528994321", "470010", "Business Savings", 2, True),
            ("Standard Bank EFT", "Standard Bank", "00192837465", "051001", "Business Current", 3, True),
            ("ABSA Bank Transfer", "ABSA Bank", "4091827364", "632005", "Cheque Account", 4, True),
            ("Nedbank EFT", "Nedbank", "1188229933", "198765", "Current Account", 5, True),
            ("TymeBank Immediate Pay", "TymeBank", "53001928371", "678910", "EveryDay Business", 6, True),
            ("FNB eWallet / Send Money", "FNB eWallet", "+27 74 568 5212", "250655", "Mobile Wallet", 7, True),
            ("Standard Bank Instant Money", "Standard Bank", "+27 74 568 5212", "051001", "Mobile Voucher", 8, True),
            ("SnapScan Merchant QR", "SnapScan", "RODZ-TUTORING-QR", "000000", "QR Merchant", 9, True),
            ("Zapper Merchant Pay", "Zapper", "ZAP-RODZ-2026", "000000", "QR Merchant", 10, False),
        ]
        result = {}
        for title, bank, acc, branch, acc_type, order, active in methods_data:
            obj, _ = PaymentMethod.objects.get_or_create(
                title=title,
                defaults={
                    "bank_name": bank,
                    "account_holder": "Rodz Tutoring (Pty) Ltd",
                    "account_number": acc,
                    "branch_code": branch,
                    "account_type": acc_type,
                    "reference_instructions": "Use your student email or cell number as your deposit reference.",
                    "additional_notes": "Upload your bank receipt or confirmation screenshot to credit coins.",
                    "is_active": active,
                    "order": order,
                },
            )
            result[title] = obj
        return result

    def _seed_content_items(self, subjects, curricula):
        items_spec = [
            # 6 PDFs (mix of free, downloadable, paid, Notes & Past Papers)
            {
                "slug": "grade-12-pure-mathematics-premium-study-pack",
                "title": "Grade 12 Pure Mathematics Premium Study Pack",
                "subject": subjects["pure-mathematics"],
                "curriculum": "CAPS & IEB",
                "curriculum_ref": curricula["CAPS"],
                "grade": "Grade 12",
                "content_type": "PDF",
                "category": "Notes",
                "description": "Differential Calculus, Cubic Functions, Optimization, Analytical Geometry, and Trigonometry with full worked solutions.",
                "cover": "caps-g12-maths.svg",
                "is_free": False,
                "allow_download": False,
                "coin_price": 50,
                "pdf": "protected_pdfs/sample_study_pack.pdf",
            },
            {
                "slug": "grade-11-mathematics-foundations-algebra",
                "title": "Grade 11 Mathematics Foundations & Algebra",
                "subject": subjects["pure-mathematics"],
                "curriculum": "CAPS & IEB",
                "curriculum_ref": curricula["CAPS"],
                "grade": "Grade 11",
                "content_type": "PDF",
                "category": "Worksheets",
                "description": "Quadratic equations, inequalities, exponents, and number patterns with step-by-step solutions.",
                "cover": "caps-g11-maths.svg",
                "is_free": False,
                "allow_download": False,
                "coin_price": 40,
                "pdf": "protected_pdfs/sample_study_pack.pdf",
            },
            {
                "slug": "grade-12-accounting-comprehensive-exam-pack",
                "title": "Grade 12 Accounting Comprehensive Exam Pack",
                "subject": subjects["accounting"],
                "curriculum": "CAPS & IEB",
                "curriculum_ref": curricula["IEB"],
                "grade": "Grade 12",
                "content_type": "PDF",
                "category": "Past Papers",
                "description": "Companies Financial Statements, Balance Sheets, Cash Flow Analysis, Fixed Assets, and Inventory Valuations.",
                "cover": "caps-accounting.svg",
                "is_free": False,
                "allow_download": False,
                "coin_price": 50,
                "pdf": "protected_pdfs/past_paper_pack.pdf",
            },
            {
                "slug": "grade-10-mathematics-essential-notes",
                "title": "Grade 10 Mathematics Essential Formulae & Notes",
                "subject": subjects["pure-mathematics"],
                "curriculum": "CAPS & IEB",
                "curriculum_ref": curricula["CAPS"],
                "grade": "Grade 10",
                "content_type": "PDF",
                "category": "Study Guides",
                "description": "Free starter pack for Grade 10 learners revising factorization, algebraic fractions, and linear equations.",
                "cover": "caps-g10-maths.svg",
                "is_free": True,
                "allow_download": True,
                "coin_price": 0,
                "pdf": "protected_pdfs/sample_study_pack.pdf",
            },
            {
                "slug": "cambridge-igcse-chemistry-revision-notes",
                "title": "Cambridge IGCSE Chemistry Stoichiometry & Bonding",
                "subject": subjects["chemistry"],
                "curriculum": "Cambridge",
                "curriculum_ref": curricula["CAMBRIDGE-IGCSE"],
                "grade": "Grade 10",
                "content_type": "PDF",
                "category": "Notes",
                "description": "Mole calculations, ionic & covalent structures, and energetics aligned to Cambridge IGCSE 0620.",
                "cover": "cambridge-physics.svg",
                "is_free": False,
                "allow_download": False,
                "coin_price": 35,
                "pdf": "protected_pdfs/sample_study_pack.pdf",
            },
            {
                "slug": "grade-9-maths-geometry-past-papers",
                "title": "Grade 9 Geometry & Equations Past Paper Pack",
                "subject": subjects["pure-mathematics"],
                "curriculum": "CAPS",
                "curriculum_ref": curricula["CAPS"],
                "grade": "Grade 9",
                "content_type": "PDF",
                "category": "Past Papers",
                "description": "Free printable past paper booklet with full step-by-step memorandum for Grade 9 learners.",
                "cover": "caps-g9-maths.svg",
                "is_free": True,
                "allow_download": True,
                "coin_price": 0,
                "pdf": "protected_pdfs/past_paper_pack.pdf",
            },
            # 4 Videos
            {
                "slug": "grade-12-physics-work-energy-power",
                "title": "Grade 12 Physical Sciences - Work, Energy & Power Breakdown",
                "subject": subjects["physical-sciences"],
                "curriculum": "CAPS & IEB",
                "curriculum_ref": curricula["CAPS"],
                "grade": "Grade 12",
                "content_type": "VIDEO",
                "category": "Video Lessons",
                "description": "Deep dive video lesson breaking down Newton's Laws, conservation of mechanical energy, and exam walkthroughs.",
                "cover": "caps-physics.svg",
                "is_free": False,
                "allow_download": False,
                "coin_price": 30,
                "youtube_url": "https://www.youtube.com/watch?v=2WS1dQ9-Bl8",
            },
            {
                "slug": "grade-12-maths-calculus-derivatives-video",
                "title": "Grade 12 Mathematics - Calculus Derivatives Masterclass",
                "subject": subjects["pure-mathematics"],
                "curriculum": "CAPS & IEB",
                "curriculum_ref": curricula["CAPS"],
                "grade": "Grade 12",
                "content_type": "VIDEO",
                "category": "Video Lessons",
                "description": "First-principles differentiation, power rule, cubic tangents, and optimization.",
                "cover": "caps-g12-maths.svg",
                "is_free": True,
                "allow_download": False,
                "coin_price": 0,
                "youtube_url": "https://www.youtube.com/watch?v=9vKqVkMQHKk",
            },
            {
                "slug": "grade-12-economics-macro-policy-video",
                "title": "Grade 12 Economics - Fiscal & Monetary Policy Lesson",
                "subject": subjects["economics"],
                "curriculum": "IEB",
                "curriculum_ref": curricula["IEB"],
                "grade": "Grade 12",
                "content_type": "VIDEO",
                "category": "Video Lessons",
                "description": "Circular flow, multiplier effect, Reserve Bank repo rate mechanics, and essay structure.",
                "cover": "caps-economics.svg",
                "is_free": False,
                "allow_download": False,
                "coin_price": 25,
                "youtube_url": "https://www.youtube.com/watch?v=1DW_g3fF3S0",
            },
            {
                "slug": "cambridge-as-accounting-cashflow-video",
                "title": "Cambridge AS Accounting - IAS 7 Cash Flow Statements",
                "subject": subjects["accounting"],
                "curriculum": "Cambridge",
                "curriculum_ref": curricula["CAMBRIDGE-AS"],
                "grade": "Grade 11",
                "content_type": "VIDEO",
                "category": "Exam Prep",
                "description": "Complete walkthrough of operating, investing, and financing cash flows under IAS 7.",
                "cover": "cambridge-accounting.svg",
                "is_free": False,
                "allow_download": False,
                "coin_price": 35,
                "youtube_url": "https://www.youtube.com/watch?v=3q7vG0z4J1A",
            },
            # 10 QUIZ items (1-to-1 with 10 Quiz objects!)
            {
                "slug": "grade-12-pure-maths-calculus-quiz",
                "title": "Grade 12 Pure Mathematics - Calculus & Functions Quiz",
                "subject": subjects["pure-mathematics"],
                "curriculum": "CAPS & IEB",
                "curriculum_ref": curricula["CAPS"],
                "grade": "Grade 12",
                "content_type": "QUIZ",
                "category": "Quiz",
                "description": "Timed assessment testing differentiation, stationary points, and cubic curve sketching.",
                "cover": "caps-exam.svg",
                "is_free": False,
                "allow_download": False,
                "coin_price": 20,
            },
            {
                "slug": "grade-12-physics-mechanics-quiz",
                "title": "Grade 12 Physical Sciences - Mechanics & Momentum Quiz",
                "subject": subjects["physical-sciences"],
                "curriculum": "CAPS",
                "curriculum_ref": curricula["CAPS"],
                "grade": "Grade 12",
                "content_type": "QUIZ",
                "category": "Quiz",
                "description": "Newton's laws, vertical projectile motion, impulse, and conservation of momentum.",
                "cover": "caps-physics.svg",
                "is_free": False,
                "allow_download": False,
                "coin_price": 20,
            },
            {
                "slug": "grade-12-accounting-ratios-quiz",
                "title": "Grade 12 Accounting - Financial Ratios & Companies Quiz",
                "subject": subjects["accounting"],
                "curriculum": "CAPS & IEB",
                "curriculum_ref": curricula["IEB"],
                "grade": "Grade 12",
                "content_type": "QUIZ",
                "category": "Quiz",
                "description": "Liquidity, solvency, gearing, and return on equity diagnostic quiz.",
                "cover": "caps-accounting.svg",
                "is_free": False,
                "allow_download": False,
                "coin_price": 20,
            },
            {
                "slug": "grade-11-algebra-quadratics-quiz",
                "title": "Grade 11 Pure Mathematics - Quadratics & Surds Quiz",
                "subject": subjects["pure-mathematics"],
                "curriculum": "CAPS",
                "curriculum_ref": curricula["CAPS"],
                "grade": "Grade 11",
                "content_type": "QUIZ",
                "category": "Quiz",
                "description": "Test discriminant nature of roots, completing the square, and exponential equations.",
                "cover": "caps-g11-maths.svg",
                "is_free": True,
                "allow_download": False,
                "coin_price": 0,
            },
            {
                "slug": "grade-12-economics-markets-quiz",
                "title": "Grade 12 Economics - Market Structures & Dynamics Quiz",
                "subject": subjects["economics"],
                "curriculum": "IEB",
                "curriculum_ref": curricula["IEB"],
                "grade": "Grade 12",
                "content_type": "QUIZ",
                "category": "Quiz",
                "description": "Perfect competition, monopoly, oligopoly, and market failure diagnostic quiz.",
                "cover": "caps-economics.svg",
                "is_free": False,
                "allow_download": False,
                "coin_price": 15,
            },
            {
                "slug": "cambridge-igcse-maths-trigonometry-quiz",
                "title": "Cambridge IGCSE Mathematics - Trigonometry & Bearings Quiz",
                "subject": subjects["cambridge-curriculum"],
                "curriculum": "Cambridge",
                "curriculum_ref": curricula["CAMBRIDGE-IGCSE"],
                "grade": "Grade 10",
                "content_type": "QUIZ",
                "category": "Quiz",
                "description": "Sine rule, cosine rule, 3-figure bearings, and area of triangles.",
                "cover": "cambridge-maths.svg",
                "is_free": False,
                "allow_download": False,
                "coin_price": 20,
            },
            {
                "slug": "grade-12-chemistry-organic-quiz",
                "title": "Grade 12 Chemistry - Organic Reactions & IUPAC Naming Quiz",
                "subject": subjects["chemistry"],
                "curriculum": "CAPS",
                "curriculum_ref": curricula["CAPS"],
                "grade": "Grade 12",
                "content_type": "QUIZ",
                "category": "Quiz",
                "description": "Alkanes, alkenes, esters, addition, elimination, and substitution reactions.",
                "cover": "cambridge-physics.svg",
                "is_free": False,
                "allow_download": False,
                "coin_price": 20,
            },
            {
                "slug": "grade-10-maths-lit-finance-quiz",
                "title": "Grade 10 Maths Literacy - Personal Finance & VAT Quiz",
                "subject": subjects["maths-literacy"],
                "curriculum": "CAPS",
                "curriculum_ref": curricula["CAPS"],
                "grade": "Grade 10",
                "content_type": "QUIZ",
                "category": "Quiz",
                "description": "Simple vs compound interest, tariff tables, and VAT calculations.",
                "cover": "caps-g10-maths.svg",
                "is_free": True,
                "allow_download": False,
                "coin_price": 0,
            },
            {
                "slug": "grade-11-life-sciences-genetics-quiz",
                "title": "Grade 11-12 Life Sciences - DNA & Genetics Quiz",
                "subject": subjects["life-sciences"],
                "curriculum": "CAPS & IEB",
                "curriculum_ref": curricula["CAPS"],
                "grade": "Grade 12",
                "content_type": "QUIZ",
                "category": "Quiz",
                "description": "DNA replication, protein synthesis, meiosis, and Mendelian inheritance.",
                "cover": "cambridge-questionbank.svg",
                "is_free": False,
                "allow_download": False,
                "coin_price": 15,
            },
            {
                "slug": "grade-12-it-algorithms-sql-quiz",
                "title": "Grade 12 Information Technology - SQL & Algorithms Quiz",
                "subject": subjects["information-technology"],
                "curriculum": "IEB",
                "curriculum_ref": curricula["IEB"],
                "grade": "Grade 12",
                "content_type": "QUIZ",
                "category": "Quiz",
                "description": "Relational database normalization, SQL joins, and Big-O sorting complexity.",
                "cover": "cambridge-mock.svg",
                "is_free": False,
                "allow_download": False,
                "coin_price": 20,
            },
        ]

        result = {}
        for spec in items_spec:
            obj, _ = ContentItem.objects.get_or_create(
                slug=spec["slug"],
                defaults={
                    "title": spec["title"],
                    "subject": spec["subject"],
                    "curriculum": spec["curriculum"],
                    "curriculum_ref": spec["curriculum_ref"],
                    "grade": spec["grade"],
                    "content_type": spec["content_type"],
                    "category": spec["category"],
                    "description": spec["description"],
                    "cover_svg_name": spec["cover"],
                    "is_free": spec["is_free"],
                    "allow_download": spec["allow_download"],
                    "coin_price": spec["coin_price"],
                    "pdf_file": spec.get("pdf", ""),
                    "youtube_url": spec.get("youtube_url", ""),
                },
            )
            result[spec["slug"]] = obj
        return result

    def _seed_courses(self, users, subjects, curricula, items):
        now = timezone.now()
        admin = users["admin"]
        courses_spec = [
            ("course-g12-calculus-mastery", "Grade 12 Calculus & Exam Mastery Bundle", users["tutor"], subjects["pure-mathematics"], "CAPS & IEB", curricula["CAPS"], "Grade 12", "caps-g12-maths.svg", 100, "APPROVED", "", ["grade-12-pure-mathematics-premium-study-pack", "grade-12-maths-calculus-derivatives-video", "grade-12-pure-maths-calculus-quiz"]),
            ("course-g12-physics-complete", "Grade 12 Physical Sciences Complete Prep", users["tutor_physics"], subjects["physical-sciences"], "CAPS & IEB", curricula["CAPS"], "Grade 12", "caps-physics.svg", 110, "APPROVED", "", ["grade-12-physics-work-energy-power", "grade-12-physics-mechanics-quiz"]),
            ("course-g12-accounting-distinction", "Grade 12 Accounting Financial Statements Pack", users["tutor_accounting"], subjects["accounting"], "CAPS & IEB", curricula["IEB"], "Grade 12", "caps-accounting.svg", 120, "APPROVED", "", ["grade-12-accounting-comprehensive-exam-pack", "grade-12-accounting-ratios-quiz"]),
            ("course-g11-algebra-bootcamp", "Grade 11 Algebra & Quadratics Bootcamp", users["peer_tutor1"], subjects["pure-mathematics"], "CAPS", curricula["CAPS"], "Grade 11", "caps-g11-maths.svg", 80, "APPROVED", "", ["grade-11-mathematics-foundations-algebra", "grade-11-algebra-quadratics-quiz"]),
            ("course-cambridge-igcse-stem", "Cambridge IGCSE STEM Foundations Bundle", users["tutor_cambridge"], subjects["cambridge-curriculum"], "Cambridge", curricula["CAMBRIDGE-IGCSE"], "Grade 10", "cambridge-maths.svg", 130, "APPROVED", "", ["cambridge-igcse-chemistry-revision-notes", "cambridge-igcse-maths-trigonometry-quiz"]),
            ("course-cambridge-as-accounting", "Cambridge AS Accounting Cash Flow Mastery", users["tutor_cambridge"], subjects["accounting"], "Cambridge", curricula["CAMBRIDGE-AS"], "Grade 11", "cambridge-accounting.svg", 95, "APPROVED", "", ["cambridge-as-accounting-cashflow-video", "grade-12-accounting-ratios-quiz"]),
            ("course-g12-economics-macro", "Grade 12 Economics Macro & Market Bundle", users["tutor_accounting"], subjects["economics"], "IEB", curricula["IEB"], "Grade 12", "caps-economics.svg", 90, "APPROVED", "", ["grade-12-economics-macro-policy-video", "grade-12-economics-markets-quiz"]),
            ("course-g10-foundations-starter", "Grade 9-10 Core Maths Starter Bundle", users["peer_tutor1"], subjects["pure-mathematics"], "CAPS", curricula["CAPS"], "Grade 10", "caps-g10-maths.svg", 60, "APPROVED", "", ["grade-10-mathematics-essential-notes", "grade-9-maths-geometry-past-papers", "grade-10-maths-lit-finance-quiz"]),
            ("course-g12-chemistry-organic-pack", "Grade 12 Organic Chemistry Intensive", users["tutor_physics"], subjects["chemistry"], "CAPS", curricula["CAPS"], "Grade 12", "cambridge-physics.svg", 105, "APPROVED", "", ["cambridge-igcse-chemistry-revision-notes", "grade-12-chemistry-organic-quiz"]),
            ("course-g12-it-lifesciences-combo", "Grade 12 IEB Sciences & Computing Bundle", users["director"], subjects["information-technology"], "IEB", curricula["IEB"], "Grade 12", "cambridge-mock.svg", 85, "APPROVED", "", ["grade-12-it-algorithms-sql-quiz", "grade-11-life-sciences-genetics-quiz"]),
            ("course-pending-maths-sprint", "Grade 12 November Final Maths Sprint", users["peer_tutor1"], subjects["pure-mathematics"], "CAPS", curricula["CAPS"], "Grade 12", "caps-exam.svg", 140, "PENDING", "", ["grade-12-pure-mathematics-premium-study-pack", "grade-12-pure-maths-calculus-quiz"]),
            ("course-rejected-draft-bundle", "Draft Mixed Revision Bundle (Needs Video)", users["peer_tutor2"], subjects["economics"], "CAPS", curricula["CAPS"], "Grade 12", "caps-economics.svg", 75, "REJECTED", "Please add at least one worked video walkthrough before resubmitting.", ["grade-12-economics-markets-quiz"]),
        ]

        result = {}
        for slug, title, creator, subj, curr_str, curr_ref, grade, cover, price, status, notes, item_slugs in courses_spec:
            course, created = Course.objects.get_or_create(
                slug=slug,
                defaults={
                    "creator": creator,
                    "title": title,
                    "subject": subj,
                    "curriculum": curr_str,
                    "curriculum_ref": curr_ref,
                    "grade": grade,
                    "description": f"Curated {grade} {subj.name} study bundle combining notes, walkthroughs, and timed quizzes.",
                    "cover_svg_name": cover,
                    "bundle_price": price,
                    "creation_fee_coins": 50,
                    "status": status,
                    "admin_notes": notes,
                    "reviewed_by": admin if status in ("APPROVED", "REJECTED") else None,
                    "reviewed_at": now if status in ("APPROVED", "REJECTED") else None,
                },
            )
            if created:
                course.items.set([items[s] for s in item_slugs if s in items])
            result[slug] = course
        return result

    def _seed_quizzes(self, items):
        quiz_bank = [
            (
                "grade-12-pure-maths-calculus-quiz",
                10,
                70,
                [
                    ("What is the derivative f'(x) of f(x) = 3x^3 - 5x + 7?", "Power rule: d/dx(3x^3 - 5x + 7) = 9x^2 - 5.", "9x^2 - 5", ["9x^3 - 5x", "6x^2 - 5", "3x^2 - 5"]),
                    ("At the stationary points of y = f(x), what is the value of f'(x)?", "A stationary point has a horizontal tangent gradient where f'(x) = 0.", "f'(x) = 0", ["f'(x) > 0", "f'(x) = 1", "f'(x) < 0"]),
                ],
            ),
            (
                "grade-12-physics-mechanics-quiz",
                15,
                60,
                [
                    ("Which physical quantity equals the area under a Net Force vs Time graph?", "Impulse J = F_net * delta_t, which equals the change in momentum.", "Impulse / Change in Momentum", ["Acceleration", "Kinetic Energy", "Work Done"]),
                    ("During an elastic collision in an isolated system, what is conserved?", "Both total linear momentum and total kinetic energy are conserved.", "Both total momentum and kinetic energy", ["Momentum only", "Kinetic energy only", "Velocity only"]),
                ],
            ),
            (
                "grade-12-accounting-ratios-quiz",
                12,
                60,
                [
                    ("Which ratio measures a company's immediate ability to pay short-term debts without selling inventory?", "The Acid-Test (Quick) ratio excludes inventories from current assets.", "Acid-test (Quick) ratio", ["Debt-equity ratio", "Return on capital employed", "Gross profit margin"]),
                    ("In a Cash Flow Statement, issuing new ordinary shares appears under which section?", "Share capital proceeds represent external financing inflows.", "Financing activities", ["Operating activities", "Investing activities", "Cash and cash equivalents"]),
                ],
            ),
            (
                "grade-11-algebra-quadratics-quiz",
                10,
                60,
                [
                    ("For ax^2 + bx + c = 0, when are the roots real and equal?", "When discriminant delta = b^2 - 4ac equals 0, there is one repeated real root.", "b^2 - 4ac = 0", ["b^2 - 4ac > 0", "b^2 - 4ac < 0", "b = 0"]),
                    ("What is the simplified value of sqrt(50) - sqrt(18)?", "5*sqrt(2) - 3*sqrt(2) = 2*sqrt(2).", "2*sqrt(2)", ["sqrt(32)", "4*sqrt(2)", "8"]),
                ],
            ),
            (
                "grade-12-economics-markets-quiz",
                10,
                60,
                [
                    ("In a perfectly competitive market, what shape is the individual firm's demand curve?", "The firm is a price taker, facing a horizontal (perfectly elastic) demand curve.", "Horizontal (perfectly elastic)", ["Downward sloping", "Vertical", "U-shaped"]),
                    ("Which monetary policy action combats high demand-pull inflation?", "Raising the repo rate increases borrowing costs and dampens aggregate demand.", "Increasing the repo rate", ["Lowering reserve requirements", "Cutting personal income tax", "Increasing government spending"]),
                ],
            ),
            (
                "cambridge-igcse-maths-trigonometry-quiz",
                15,
                65,
                [
                    ("Which formula finds the area of triangle ABC given sides a, b and included angle C?", "Area = 1/2 * a * b * sin(C).", "0.5 * a * b * sin(C)", ["a * b * cos(C)", "0.5 * a * b * tan(C)", "a^2 + b^2 - 2ab cos(C)"]),
                    ("A bearing is measured clockwise from which direction as a 3-digit angle?", "True bearings always start clockwise from North (000 deg).", "North", ["East", "South", "West"]),
                ],
            ),
            (
                "grade-12-chemistry-organic-quiz",
                12,
                60,
                [
                    ("Which functional group characterizes an ester formed from an alcohol and carboxylic acid?", "Esters contain the -COO- (ester) functional group.", "-COO-", ["-OH", "-CHO", "-NH2"]),
                    ("Which catalyst is typically used for the hydration of ethene to ethanol?", "Acid-catalyzed addition of steam uses H3PO4 or H2SO4.", "Dilute sulfuric or phosphoric acid", ["Nickel at 150 C", "UV light", "Concentrated NaOH"]),
                ],
            ),
            (
                "grade-10-maths-lit-finance-quiz",
                10,
                60,
                [
                    ("In South Africa, what is the standard Value-Added Tax (VAT) rate?", "Standard VAT rate is 15%.", "15%", ["14%", "10%", "18%"]),
                    ("Which type of interest earns interest on previously accumulated interest?", "Compound interest grows exponentially on principal plus prior interest.", "Compound interest", ["Simple interest", "Flat-rate discount", "Fixed tariff"]),
                ],
            ),
            (
                "grade-11-life-sciences-genetics-quiz",
                12,
                60,
                [
                    ("Which nitrogenous base pairs with Adenine (A) in a DNA double helix?", "In DNA, Adenine pairs with Thymine (A-T) via two hydrogen bonds.", "Thymine (T)", ["Uracil (U)", "Cytosine (C)", "Guanine (G)"]),
                    ("During which process does crossing over occur to increase genetic variation?", "Crossing over takes place during Prophase I of Meiosis.", "Prophase I of Meiosis", ["Mitosis Metaphase", "DNA Replication", "Telophase II"]),
                ],
            ),
            (
                "grade-12-it-algorithms-sql-quiz",
                15,
                65,
                [
                    ("Which SQL clause filters grouped rows after an aggregate function like COUNT()?", "HAVING filters aggregated groups, whereas WHERE filters individual rows.", "HAVING", ["WHERE", "ORDER BY", "DISTINCT"]),
                    ("What is the average time complexity of Binary Search on a sorted array?", "Halving the search space each step yields O(log n).", "O(log n)", ["O(n)", "O(n^2)", "O(1)"]),
                ],
            ),
        ]

        result = {}
        for slug, limit, pass_pct, questions in quiz_bank:
            c_item = items[slug]
            quiz, _ = Quiz.objects.get_or_create(
                content_item=c_item,
                defaults={
                    "title": c_item.title,
                    "instructions": f"Timed diagnostic assessment ({limit} minutes). Pass mark: {pass_pct}%.",
                    "time_limit_minutes": limit,
                    "pass_percentage": pass_pct,
                },
            )
            for idx, (q_text, expl, correct_txt, distractors) in enumerate(questions):
                q_obj, _ = Question.objects.get_or_create(
                    quiz=quiz,
                    order=idx,
                    defaults={"text": q_text, "explanation": expl},
                )
                if q_obj.choices.count() == 0:
                    Choice.objects.create(question=q_obj, text=correct_txt, is_correct=True)
                    for d_txt in distractors:
                        Choice.objects.create(question=q_obj, text=d_txt, is_correct=False)
            result[slug] = quiz
        return result

    def _seed_quiz_attempts(self, users, quizzes):
        quiz_list = list(quizzes.values())
        attempt_specs = [
            (users["student"], quiz_list[0], 2, 2, 100.0, True),
            (users["student"], quiz_list[1], 2, 1, 50.0, False),
            (users["student"], quiz_list[2], 2, 2, 100.0, True),
            (users["student"], quiz_list[3], 2, 2, 100.0, True),
            (users["student_g7"], quiz_list[7], 2, 2, 100.0, True),
            (users["student_g8"], quiz_list[3], 2, 1, 50.0, False),
            (users["student_g9"], quiz_list[5], 2, 2, 100.0, True),
            (users["student_g10"], quiz_list[7], 2, 2, 100.0, True),
            (users["student_g10"], quiz_list[5], 2, 1, 50.0, False),
            (users["student_g11"], quiz_list[3], 2, 2, 100.0, True),
            (users["student_g11"], quiz_list[0], 2, 2, 100.0, True),
            (users["peer_tutor1"], quiz_list[6], 2, 2, 100.0, True),
            (users["peer_tutor2"], quiz_list[4], 2, 2, 100.0, True),
            (users["pending1"], quiz_list[0], 2, 2, 100.0, True),
            (users["pending2"], quiz_list[8], 2, 2, 100.0, True),
        ]
        for student, quiz, total, correct, pct, passed in attempt_specs:
            if not QuizAttempt.objects.filter(student=student, quiz=quiz, score_percent=pct).exists():
                QuizAttempt.objects.create(
                    student=student,
                    quiz=quiz,
                    total_questions=total,
                    correct_answers=correct,
                    score_percent=pct,
                    passed=passed,
                )

    def _seed_wallet_activity(self, users, system_wallet, bundles, methods, items, courses):
        admin = users["admin"]
        now = timezone.now()

        # 1. ContentUnlocks (14 records)
        unlock_items_pairs = [
            (users["student"], items["grade-12-pure-mathematics-premium-study-pack"], 50),
            (users["student"], items["grade-12-physics-work-energy-power"], 30),
            (users["student"], items["grade-12-pure-maths-calculus-quiz"], 20),
            (users["student_g11"], items["grade-11-mathematics-foundations-algebra"], 40),
            (users["student_g11"], items["cambridge-as-accounting-cashflow-video"], 35),
            (users["student_g10"], items["cambridge-igcse-chemistry-revision-notes"], 35),
            (users["student_g10"], items["cambridge-igcse-maths-trigonometry-quiz"], 20),
            (users["student_g9"], items["cambridge-igcse-maths-trigonometry-quiz"], 20),
            (users["student_g8"], items["grade-11-mathematics-foundations-algebra"], 40),
            (users["student_g7"], items["grade-12-economics-markets-quiz"], 15),
            (users["pending1"], items["grade-12-accounting-comprehensive-exam-pack"], 50),
            (users["pending2"], items["grade-11-life-sciences-genetics-quiz"], 15),
            (users["peer_tutor1"], items["grade-12-it-algorithms-sql-quiz"], 20),
            (users["peer_tutor2"], items["grade-12-economics-macro-policy-video"], 25),
        ]
        for user, item, spent in unlock_items_pairs:
            ContentUnlock.objects.get_or_create(
                user=user,
                content_item=item,
                defaults={"coins_spent": spent},
            )

        # 2. CourseUnlocks (12 records)
        approved_courses = [
            courses["course-g12-calculus-mastery"],
            courses["course-g12-physics-complete"],
            courses["course-g12-accounting-distinction"],
            courses["course-g11-algebra-bootcamp"],
            courses["course-cambridge-igcse-stem"],
            courses["course-cambridge-as-accounting"],
            courses["course-g12-economics-macro"],
            courses["course-g10-foundations-starter"],
            courses["course-g12-chemistry-organic-pack"],
            courses["course-g12-it-lifesciences-combo"],
        ]
        course_unlock_pairs = [
            (users["student"], approved_courses[0], 100),
            (users["student"], approved_courses[1], 110),
            (users["student_g11"], approved_courses[3], 80),
            (users["student_g11"], approved_courses[5], 95),
            (users["student_g10"], approved_courses[7], 60),
            (users["student_g10"], approved_courses[4], 130),
            (users["student_g9"], approved_courses[4], 130),
            (users["student_g8"], approved_courses[3], 80),
            (users["student_g7"], approved_courses[7], 60),
            (users["pending1"], approved_courses[2], 120),
            (users["pending2"], approved_courses[8], 105),
            (users["peer_tutor2"], approved_courses[6], 90),
        ]
        for user, course, spent in course_unlock_pairs:
            CourseUnlock.objects.get_or_create(
                user=user,
                course=course,
                defaults={"coins_spent": spent},
            )

        # 3. CoinPaymentRequests (12 records across APPROVED, PENDING, REJECTED)
        bundle_list = list(bundles.values())
        method_list = list(methods.values())
        payment_specs = [
            ("RODZ-SEED-REQ-001", users["student"], bundle_list[1], method_list[0], "APPROVED", "Verified via FNB statement."),
            ("RODZ-SEED-REQ-002", users["student_g11"], bundle_list[2], method_list[1], "APPROVED", "Verified via Capitec Instant EFT."),
            ("RODZ-SEED-REQ-003", users["student_g10"], bundle_list[0], method_list[2], "APPROVED", "Standard Bank EFT cleared."),
            ("RODZ-SEED-REQ-004", users["student_g9"], bundle_list[1], method_list[3], "APPROVED", "ABSA receipt matched."),
            ("RODZ-SEED-REQ-005", users["student_g8"], bundle_list[4], method_list[4], "APPROVED", "Nedbank proof approved."),
            ("RODZ-SEED-REQ-006", users["student_g7"], bundle_list[0], method_list[5], "APPROVED", "TymeBank instant deposit confirmed."),
            ("RODZ-SEED-REQ-007", users["student"], bundle_list[3], method_list[0], "PENDING", ""),
            ("RODZ-SEED-REQ-008", users["student_g11"], bundle_list[5], method_list[1], "PENDING", ""),
            ("RODZ-SEED-REQ-009", users["pending1"], bundle_list[0], method_list[6], "PENDING", ""),
            ("RODZ-SEED-REQ-010", users["student_g10"], bundle_list[6], method_list[8], "PENDING", ""),
            ("RODZ-SEED-REQ-011", users["rejected1"], bundle_list[0], method_list[0], "REJECTED", "Duplicate reference number submitted; please upload updated receipt."),
            ("RODZ-SEED-REQ-012", users["rejected2"], bundle_list[1], method_list[1], "REJECTED", "Deposit amount did not match selected bundle."),
        ]
        for ref, student, bundle, method, status, notes in payment_specs:
            CoinPaymentRequest.objects.get_or_create(
                reference_number=ref,
                defaults={
                    "student": student,
                    "bundle": bundle,
                    "payment_method": method,
                    "coins_to_credit": bundle.coins,
                    "amount_paid": bundle.price_zar,
                    "bundle_name_snapshot": bundle.name,
                    "bundle_price_snapshot": bundle.price_zar,
                    "proof_of_payment": "payment_proofs/seed_pop_receipt.pdf",
                    "student_notes": f"Deposit for {bundle.name} ({ref})",
                    "status": status,
                    "admin_notes": notes,
                    "reviewed_by": admin if status in ("APPROVED", "REJECTED") else None,
                    "reviewed_at": now if status in ("APPROVED", "REJECTED") else None,
                },
            )

        # 4. CoinPriceChangeLog (10 records)
        price_logs_spec = [
            (bundle_list[0], Decimal("55.00"), Decimal("60.00"), "Seed Q3 annual CPI tariff alignment (Starter Pack)"),
            (bundle_list[1], Decimal("100.00"), Decimal("110.00"), "Seed Q3 bonus coin margin update (Most Popular)"),
            (bundle_list[2], Decimal("200.00"), Decimal("220.00"), "Seed Q3 multi-subject bundle adjustment"),
            (bundle_list[3], Decimal("400.00"), Decimal("420.00"), "Seed Q3 annual scholarship tier revision"),
            (bundle_list[4], Decimal("80.00"), Decimal("85.00"), "Seed weekend cram pack update"),
            (bundle_list[5], Decimal("150.00"), Decimal("165.00"), "Seed exam blitz pack seasonal calibration"),
            (bundle_list[6], Decimal("260.00"), Decimal("275.00"), "Seed study group pack calibration"),
            (bundle_list[7], Decimal("320.00"), Decimal("340.00"), "Seed Cambridge A-Level resource inclusion"),
            (bundle_list[8], Decimal("125.00"), Decimal("135.00"), "Seed Olympiad coaching pack update"),
            (bundle_list[9], Decimal("500.00"), Decimal("520.00"), "Seed Holiday bootcamp bundle review"),
        ]
        for bundle, old_p, new_p, reason in price_logs_spec:
            CoinPriceChangeLog.objects.get_or_create(
                bundle_name=bundle.name,
                change_reason=reason,
                defaults={
                    "bundle": bundle,
                    "coins": bundle.coins,
                    "old_price_zar": old_p,
                    "new_price_zar": new_p,
                    "old_rate_per_coin": round(old_p / bundle.coins, 4),
                    "new_rate_per_coin": round(new_p / bundle.coins, 4),
                    "changed_by": admin,
                },
            )

        # 5. Seeded CoinTransactions (guarded by unique description so balances stay exact)
        ledger_specs = [
            (users["student"], 130, "PAYMENT_APPROVED", "Seed POP Approved: RODZ-SEED-REQ-001", admin, None),
            (users["student"], -50, "CONTENT_UNLOCK", "Seed Unlock: Grade 12 Pure Maths Study Pack", None, None),
            (users["student"], -100, "COURSE_UNLOCK", "Seed Course Unlock: Calculus Mastery Bundle", None, users["tutor"]),
            (users["tutor"], 100, "CREATOR_EARNING", "Seed Creator Earning: Calculus Mastery Bundle", None, users["student"]),
            (users["student_g11"], 280, "PAYMENT_APPROVED", "Seed POP Approved: RODZ-SEED-REQ-002", admin, None),
            (users["student_g11"], -80, "COURSE_UNLOCK", "Seed Course Unlock: Grade 11 Algebra Bootcamp", None, users["peer_tutor1"]),
            (users["peer_tutor1"], 80, "CREATOR_EARNING", "Seed Creator Earning: Grade 11 Algebra Bootcamp", None, users["student_g11"]),
            (users["peer_tutor1"], -50, "COURSE_FEE", "Seed Course Creation Deposit: Grade 11 Bootcamp", None, None),
            (users["student_g10"], 60, "PAYMENT_APPROVED", "Seed POP Approved: RODZ-SEED-REQ-003", admin, None),
            (users["student_g10"], -20, "CONTENT_UNLOCK", "Seed Unlock: Cambridge IGCSE Trigonometry Quiz", None, None),
            (users["student_g9"], 130, "PAYMENT_APPROVED", "Seed POP Approved: RODZ-SEED-REQ-004", admin, None),
            (users["student_g8"], 90, "PAYMENT_APPROVED", "Seed POP Approved: RODZ-SEED-REQ-005", admin, None),
            (users["student_g7"], 60, "PAYMENT_APPROVED", "Seed POP Approved: RODZ-SEED-REQ-006", admin, None),
            (users["tutor_cambridge"], 150, "ADMIN_CREDIT", "Seed Tutor Merit Bonus: Cambridge Material", admin, None),
            (users["tutor_physics"], -60, "COIN_SALE", "Seed Cash-Out Redemption: Physics Tutor Payout", None, None),
            (users["student"], -22, "TRANSFER_SENT", "Seed P2P Transfer to student.g11 (incl. 2 coin fee)", users["student"], users["student_g11"]),
            (users["student_g11"], 20, "TRANSFER_RECEIVED", "Seed P2P Transfer from student@rodztutoring.co.za", users["student"], users["student"]),
            (users["tutor_accounting"], 45, "REFUND", "Seed Admin Adjustment: Course Hosting Credit", admin, None),
        ]
        for user, amount, tx_type, desc, actor, counterparty in ledger_specs:
            wallet, _ = StudentWallet.objects.get_or_create(user=user)
            if not CoinTransaction.objects.filter(wallet=wallet, description=desc).exists():
                if amount < 0 and wallet.coins < abs(amount):
                    # Ensure positive balance before recording seeded debit
                    wallet.coins += abs(amount)
                    wallet.save()
                wallet.coins += amount
                wallet.save()
                CoinTransaction.objects.create(
                    wallet=wallet,
                    amount=amount,
                    transaction_type=tx_type,
                    description=desc,
                    created_by=actor,
                    counterparty=counterparty,
                )
