from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import CustomUser
from wallet.models import StudentWallet, CoinTransaction, CoinBundle, PaymentMethod, CoinPaymentRequest


class WalletTestCase(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='walletuser@example.com',
            password='Password123!',
            is_student=True
        )
        self.admin = CustomUser.objects.create_superuser(
            email='adminuser@example.com',
            password='AdminPassword123!'
        )
        self.client = Client()

    def test_auto_created_wallet(self):
        wallet = StudentWallet.objects.get(user=self.user)
        self.assertEqual(wallet.coins, 0)

    def test_credit_and_debit_coins(self):
        wallet = StudentWallet.objects.get(user=self.user)
        wallet.credit_coins(100, description="EFT Payment Pack")
        self.assertEqual(wallet.coins, 100)
        self.assertEqual(CoinTransaction.objects.filter(wallet=wallet).count(), 1)

        wallet.debit_coins(40, description="Unlocked Maths Pack")
        self.assertEqual(wallet.coins, 60)
        self.assertEqual(CoinTransaction.objects.filter(wallet=wallet).count(), 2)

    def test_cannot_overdraw(self):
        wallet = StudentWallet.objects.get(user=self.user)
        wallet.credit_coins(30)
        with self.assertRaises(ValueError):
            wallet.debit_coins(50)

    def test_payment_request_and_admin_approval(self):
        bundle = CoinBundle.objects.create(
            name="Term Booster",
            coins=120,
            price_zar=110.00,
            badge="POPULAR",
            order=1
        )
        pm = PaymentMethod.objects.create(
            title="FNB Bank Transfer",
            bank_name="First National Bank",
            account_number="62891234567",
            order=1
        )

        dummy_file = SimpleUploadedFile("pop_receipt.pdf", b"%PDF-1.4 dummy content", content_type="application/pdf")

        # 1. Student submits payment request
        self.client.login(email='walletuser@example.com', password='Password123!')
        response = self.client.post(reverse('wallet:buy_coins'), {
            'bundle': bundle.id,
            'payment_method': pm.id,
            'reference_number': 'FNB-998877',
            'proof_of_payment': dummy_file,
            'student_notes': 'Paid via FNB online app',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        req = CoinPaymentRequest.objects.get(reference_number='FNB-998877')
        self.assertEqual(req.status, 'PENDING')
        self.assertEqual(req.coins_to_credit, 120)
        self.assertEqual(req.amount_paid, 110.00)

        # 2. Admin approves request
        self.client.login(email='adminuser@example.com', password='AdminPassword123!')
        approve_resp = self.client.post(reverse('wallet:admin_payment_requests'), {
            'action': 'approve',
            'request_id': req.id,
            'admin_notes': 'Verified on FNB statement'
        }, follow=True)

        req.refresh_from_db()
        self.assertEqual(req.status, 'APPROVED')

        wallet = StudentWallet.objects.get(user=self.user)
        self.assertEqual(wallet.coins, 120)

    def test_content_unlock_retention(self):
        from content_hub.models import ContentItem, Subject
        from wallet.models import ContentUnlock
        subject = Subject.objects.create(name='Maths Retention', slug='maths-retention')
        item = ContentItem.objects.create(
            title='Retained Study Pack',
            slug='retained-study-pack',
            subject=subject,
            coin_price=50
        )
        wallet = StudentWallet.objects.get(user=self.user)
        wallet.credit_coins(100)

        unlock = ContentUnlock.objects.create(user=self.user, content_item=item, coins_spent=50)
        self.assertTrue(unlock.is_active)
        self.assertIsNotNone(unlock.expires_at)
        self.assertTrue(self.user.has_unlocked(item))

    def test_unlock_item_insufficient_coins(self):
        from content_hub.models import ContentItem, Subject
        subject = Subject.objects.create(name='Science', slug='science-test')
        item = ContentItem.objects.create(
            title='Physics Pack',
            slug='physics-pack-test',
            subject=subject,
            coin_price=80
        )
        self.client.login(email='walletuser@example.com', password='Password123!')
        url = reverse('wallet:unlock_item', kwargs={'item_slug': item.slug})
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.user.has_unlocked(item))
        wallet = StudentWallet.objects.get(user=self.user)
        self.assertEqual(wallet.coins, 0)

    def test_unlock_item_sufficient_coins(self):
        from content_hub.models import ContentItem, Subject
        subject = Subject.objects.create(name='Biology', slug='biology-test')
        item = ContentItem.objects.create(
            title='Genetics Revision',
            slug='genetics-revision-test',
            subject=subject,
            coin_price=45
        )
        wallet = StudentWallet.objects.get(user=self.user)
        wallet.credit_coins(100)

        self.client.login(email='walletuser@example.com', password='Password123!')
        url = reverse('wallet:unlock_item', kwargs={'item_slug': item.slug})
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.user.has_unlocked(item))
        wallet.refresh_from_db()
        self.assertEqual(wallet.coins, 55)

    def test_admin_credit_panel_access_and_action(self):
        # 1. Non-admin is blocked
        self.client.login(email='walletuser@example.com', password='Password123!')
        url = reverse('wallet:admin_credit_panel')
        res_blocked = self.client.get(url)
        self.assertNotEqual(res_blocked.status_code, 200)

        # 2. Admin is allowed and can credit coins
        self.client.login(email='adminuser@example.com', password='AdminPassword123!')
        res_admin = self.client.get(url)
        self.assertEqual(res_admin.status_code, 200)

        res_credit = self.client.post(url, {
            'student_email': self.user.email,
            'coin_amount': '75',
            'note': 'Bursary topup'
        }, follow=True)
        self.assertEqual(res_credit.status_code, 200)

        wallet = StudentWallet.objects.get(user=self.user)
        self.assertEqual(wallet.coins, 75)

    def test_student_personal_coin_history(self):
        wallet = StudentWallet.objects.get(user=self.user)
        wallet.credit_coins(50, description="Welcome gift bonus", transaction_type='BONUS')

        self.client.login(email='walletuser@example.com', password='Password123!')
        url = reverse('wallet:coin_history')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'MY COIN TRANSACTION HISTORY')
        self.assertContains(response, 'Welcome gift bonus')
        self.assertContains(response, '+50 Coins')

    def test_admin_global_coin_transactions_ledger(self):
        # Create a second student with transactions
        other_student = CustomUser.objects.create_user(
            email='other_learner@example.com',
            password='Password123!',
            is_student=True
        )
        other_wallet = StudentWallet.objects.get(user=other_student)
        other_wallet.credit_coins(120, description="Term booster deposit", transaction_type='PAYMENT_APPROVED')

        self.client.login(email='adminuser@example.com', password='AdminPassword123!')
        # Admin accessing global ledger
        url = reverse('wallet:coin_history')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'GLOBAL COIN TRANSACTIONS LEDGER')
        self.assertContains(response, 'other_learner@example.com')
        self.assertContains(response, 'Term booster deposit')
        self.assertContains(response, 'Coins in Circulation')

    def test_coin_history_filtering_and_search(self):
        wallet = StudentWallet.objects.get(user=self.user)
        wallet.credit_coins(80, description="Maths competition award", transaction_type='ADMIN_CREDIT')
        wallet.debit_coins(30, description="Science Pack Unlock", transaction_type='CONTENT_UNLOCK')

        self.client.login(email='adminuser@example.com', password='AdminPassword123!')
        url = reverse('wallet:coin_history')

        # Filter by CREDIT
        res_credit = self.client.get(f"{url}?type=CREDIT")
        self.assertEqual(res_credit.status_code, 200)
        self.assertContains(res_credit, 'Maths competition award')

        # Search by description
        res_search = self.client.get(f"{url}?q=Science+Pack")
        self.assertEqual(res_search.status_code, 200)
        self.assertContains(res_search, 'Science Pack Unlock')
        self.assertNotContains(res_search, 'Maths competition award')

        # Filter by specific user
        res_user = self.client.get(f"{url}?user_id={self.user.id}")
        self.assertEqual(res_user.status_code, 200)
        self.assertContains(res_user, self.user.email)


