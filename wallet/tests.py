from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import CustomUser
from wallet.models import (
    StudentWallet, CoinTransaction, CoinBundle, PaymentMethod, 
    CoinPaymentRequest, CoinPriceChangeLog, CoinWallet, SystemWallet
)


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

    def test_coin_wallet_alias(self):
        """Ensure CoinWallet alias is identical to StudentWallet."""
        self.assertIs(CoinWallet, StudentWallet)
        wallet = CoinWallet.objects.get(user=self.user)
        self.assertIsInstance(wallet, StudentWallet)

    def test_peer_to_peer_transfer_success(self):
        """User transfers coins directly to another user instantly without admin."""
        recipient = CustomUser.objects.create_user(
            email='recipient_learner@example.com',
            password='Password123!',
            full_name='Thabo Mokoena'
        )
        sender_wallet = StudentWallet.objects.get(user=self.user)
        recipient_wallet = StudentWallet.objects.get(user=recipient)

        # Give sender coins
        sender_wallet.credit_coins(100, description="Initial balance")
        self.assertEqual(sender_wallet.coins, 100)
        self.assertEqual(recipient_wallet.coins, 0)

        # Instant P2P transfer
        tx_sent, tx_rcv = sender_wallet.transfer_coins_to(recipient, 35, note="Maths Study Group Help")

        # Assert balances updated immediately (100 - (35 + 2 fee) = 63)
        sender_wallet.refresh_from_db()
        recipient_wallet.refresh_from_db()
        self.assertEqual(sender_wallet.coins, 63)
        self.assertEqual(recipient_wallet.coins, 35)

        # Assert transactions (-35 sent - 2 fee = -37)
        self.assertEqual(tx_sent.amount, -37)
        self.assertEqual(tx_sent.transaction_type, 'TRANSFER_SENT')
        self.assertEqual(tx_sent.counterparty, recipient)
        self.assertTrue(tx_sent.is_transfer)

        self.assertEqual(tx_rcv.amount, 35)
        self.assertEqual(tx_rcv.transaction_type, 'TRANSFER_RECEIVED')
        self.assertEqual(tx_rcv.counterparty, self.user)
        self.assertTrue(tx_rcv.is_transfer)

    def test_peer_to_peer_insufficient_balance(self):
        """Cannot transfer more coins than available."""
        recipient = CustomUser.objects.create_user(
            email='recipient2@example.com',
            password='Password123!'
        )
        sender_wallet = StudentWallet.objects.get(user=self.user)
        sender_wallet.credit_coins(10)

        with self.assertRaises(ValueError):
            sender_wallet.transfer_coins_to(recipient, 50, note="Too much")

    def test_peer_to_peer_self_transfer_blocked(self):
        """Cannot transfer coins to oneself."""
        sender_wallet = StudentWallet.objects.get(user=self.user)
        sender_wallet.credit_coins(50)

        with self.assertRaises(ValueError):
            sender_wallet.transfer_coins_to(self.user, 10)

    def test_transfer_coins_view_ajax(self):
        """Test transfer view with AJAX and JSON response."""
        recipient = CustomUser.objects.create_user(
            email='peer_ajax@example.com',
            password='Password123!',
            full_name='Ayanda'
        )
        sender_wallet = StudentWallet.objects.get(user=self.user)
        sender_wallet.credit_coins(100)

        self.client.login(email='walletuser@example.com', password='Password123!')
        url = reverse('wallet:transfer_coins')

        # 1. Valid transfer
        response = self.client.post(url, {
            'recipient_email': 'peer_ajax@example.com',
            'amount': '25',
            'note': 'Quiz partnership'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        # 100 - (25 + 2 fee) = 73
        self.assertEqual(data['remaining_coins'], 73)

        # 2. Prevent self transfer
        res_self = self.client.post(url, {
            'recipient_email': self.user.email,
            'amount': '10'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res_self.status_code, 400)
        self.assertFalse(res_self.json()['success'])

        # 3. Prevent overdraft
        res_overdraft = self.client.post(url, {
            'recipient_email': 'peer_ajax@example.com',
            'amount': '500'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res_overdraft.status_code, 400)
        self.assertFalse(res_overdraft.json()['success'])

    def test_non_admin_privacy_masks_admin_identity(self):
        """Non-admin must never see the admin who credited/debited coins, but sees peer in transfers."""
        # 1. Admin credits user with note
        wallet = StudentWallet.objects.get(user=self.user)
        tx = wallet.credit_coins(
            50, 
            description="Special merit award", 
            admin_user=self.admin, 
            transaction_type='ADMIN_CREDIT'
        )
        self.assertEqual(tx.created_by, self.admin)
        self.assertIn("Special merit award", tx.get_clean_description)

        # 2. Peer transfer
        peer = CustomUser.objects.create_user(
            email='friend@example.com',
            password='Password123!',
            full_name='FriendName'
        )
        peer_wallet = StudentWallet.objects.get(user=peer)
        peer_wallet.credit_coins(50)
        peer_wallet.transfer_coins_to(self.user, 20, note="Study share")

        # 3. Student views their coin history
        self.client.login(email='walletuser@example.com', password='Password123!')
        url = reverse('wallet:coin_history')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Student MUST NOT see admin's email or identity
        self.assertNotContains(response, self.admin.email)
        self.assertContains(response, 'Rodz Tutoring Platform')

        # Student DOES see peer's name/email on transfer
        self.assertContains(response, 'FriendName')

    def test_admin_views_full_audit_details(self):
        """Admin viewing coin transactions ledger must see full audit details including admin emails."""
        wallet = StudentWallet.objects.get(user=self.user)
        wallet.credit_coins(50, description="Bonus grant", admin_user=self.admin, transaction_type='ADMIN_CREDIT')

        self.client.login(email='adminuser@example.com', password='AdminPassword123!')
        url = reverse('wallet:coin_history')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Admin CAN see which admin issued the credit
        self.assertContains(response, self.admin.email)

    def test_historical_purchase_rate_snapshot(self):
        """Payment request retains the exact rate_per_coin and bundle price at purchase time."""
        bundle = CoinBundle.objects.create(
            name="Mega Bundle",
            coins=200,
            price_zar=Decimal('150.00'),
            order=1
        )
        # Bundle rate is 150 / 200 = 0.7500
        self.assertEqual(bundle.rate_per_coin, Decimal('0.7500'))

        pm = PaymentMethod.objects.create(
            title="Capitec Pay",
            account_number="123456"
        )
        req = CoinPaymentRequest.objects.create(
            student=self.user,
            bundle=bundle,
            payment_method=pm,
            coins_to_credit=bundle.coins,
            amount_paid=bundle.price_zar,
            reference_number="REF-SNAP-01"
        )
        self.assertEqual(req.rate_per_coin, Decimal('0.7500'))
        self.assertEqual(req.bundle_name_snapshot, "Mega Bundle")
        self.assertEqual(req.bundle_price_snapshot, Decimal('150.00'))

        # Later, Admin changes bundle price to R250.00
        bundle.price_zar = Decimal('250.00')
        bundle.save()
        self.assertEqual(bundle.rate_per_coin, Decimal('1.2500'))

        # The historical purchase request MUST NOT change
        req.refresh_from_db()
        self.assertEqual(req.rate_per_coin, Decimal('0.7500'))
        self.assertEqual(req.bundle_price_snapshot, Decimal('150.00'))

    def test_coin_bundle_pricing_view_and_change_log(self):
        """Admin adjusts bundle price in admin pricing view and price change is logged."""
        bundle = CoinBundle.objects.create(
            name="Pro Learner Pack",
            coins=100,
            price_zar=Decimal('90.00')
        )
        url = reverse('wallet:admin_pricing')

        # 1. Non-admin is blocked
        self.client.login(email='walletuser@example.com', password='Password123!')
        res_blocked = self.client.get(url)
        self.assertNotEqual(res_blocked.status_code, 200)

        # 2. Admin adjusts price
        self.client.login(email='adminuser@example.com', password='AdminPassword123!')
        res_post = self.client.post(url, {
            'bundle_id': bundle.id,
            'price_zar': '120.00',
            'change_reason': 'Annual inflation rate adjustment'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(res_post.status_code, 200)
        data = res_post.json()
        self.assertTrue(data['success'])

        bundle.refresh_from_db()
        self.assertEqual(bundle.price_zar, Decimal('120.00'))

        # Verify audit log created
        log = CoinPriceChangeLog.objects.filter(bundle=bundle).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.old_price_zar, Decimal('90.00'))
        self.assertEqual(log.new_price_zar, Decimal('120.00'))
        self.assertEqual(log.changed_by, self.admin)
        self.assertEqual(log.change_reason, 'Annual inflation rate adjustment')

    def test_system_wallet_singleton_and_treasury(self):
        """SystemWallet singleton handles central currency, fees, deduction for purchase and addition on sale."""
        sys_wallet = SystemWallet.get_instance()
        initial_coins = sys_wallet.coins
        self.assertGreater(initial_coins, 0)
        self.assertEqual(sys_wallet.currency_code, 'ZAR')
        self.assertEqual(sys_wallet.currency_symbol, 'R')

        # 1. Deduct for student purchase
        student_wallet = StudentWallet.objects.get(user=self.user)
        sys_wallet.deduct_for_purchase(student_wallet, 150, description="150 Coin Purchase")
        sys_wallet.refresh_from_db()
        student_wallet.refresh_from_db()

        self.assertEqual(sys_wallet.coins, initial_coins - 150)
        self.assertEqual(student_wallet.coins, 150)
        self.assertEqual(sys_wallet.total_coins_distributed, 150)

        # 2. Add from seller cash-out
        sys_wallet.add_from_sale(student_wallet, 50, description="Cash out sale")
        sys_wallet.refresh_from_db()
        student_wallet.refresh_from_db()

        self.assertEqual(student_wallet.coins, 100)
        self.assertEqual(sys_wallet.coins, initial_coins - 100)
        self.assertEqual(sys_wallet.total_coins_redeemed, 50)

    def test_peer_transfer_deducts_fee_to_system_wallet(self):
        """Peer transfer debits amount + fee from sender, credits amount to recipient, and fee to SystemWallet."""
        sender_wallet = StudentWallet.objects.get(user=self.user)
        sender_wallet.credit_coins(100)

        recipient_user = CustomUser.objects.create_user(
            email='recipient_fee@example.com',
            password='Password123!',
            is_student=True
        )
        recipient_wallet = StudentWallet.objects.get(user=recipient_user)

        sys_wallet = SystemWallet.get_instance()
        initial_fees = sys_wallet.total_fees_collected
        initial_sys_coins = sys_wallet.coins

        # Sender transfers 40 coins (fee is 2 coins)
        tx_sender, tx_rcv = sender_wallet.transfer_coins_to(recipient_user, 40, note="Study share")

        sender_wallet.refresh_from_db()
        recipient_wallet.refresh_from_db()
        sys_wallet.refresh_from_db()

        self.assertEqual(sender_wallet.coins, 58)  # 100 - (40 + 2)
        self.assertEqual(recipient_wallet.coins, 40)
        self.assertEqual(sys_wallet.total_fees_collected, initial_fees + 2)
        self.assertEqual(sys_wallet.coins, initial_sys_coins + 2)

        # Sender cannot transfer 58 coins because 58 + 2 = 60 > 58
        with self.assertRaises(ValueError):
            sender_wallet.transfer_coins_to(recipient_user, 58)

    def test_course_unlock_credits_creator(self):
        """Unlocking a course bundle credits the course creator wallet."""
        from content_hub.models import Course, Subject
        tutor = CustomUser.objects.create_user(
            email='course_tutor@example.com',
            password='Password123!',
            is_tutor=True
        )
        tutor_wallet = StudentWallet.objects.get(user=tutor)
        subject = Subject.objects.create(name='Physics', slug='physics')

        course = Course.objects.create(
            creator=tutor,
            title='Physics Complete Pack',
            slug='physics-complete-pack',
            subject=subject,
            bundle_price=80,
            status='APPROVED'
        )

        student_wallet = StudentWallet.objects.get(user=self.user)
        student_wallet.credit_coins(100)

        self.client.login(email='walletuser@example.com', password='Password123!')
        url = reverse('wallet:unlock_course', kwargs={'course_slug': course.slug})

        resp = self.client.post(url, follow=True)
        self.assertEqual(resp.status_code, 200)

        student_wallet.refresh_from_db()
        tutor_wallet.refresh_from_db()

        self.assertEqual(student_wallet.coins, 20)  # 100 - 80
        self.assertEqual(tutor_wallet.coins, 80)    # Credited to creator

        # Check transaction type
        tx = CoinTransaction.objects.filter(wallet=tutor_wallet, transaction_type='CREATOR_EARNING').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 80)

    def test_admin_financial_settings_and_bundle_management(self):
        """Admin updates financial settings, creates a bundle, edits it, and deletes it."""
        self.client.login(email='adminuser@example.com', password='AdminPassword123!')
        url = reverse('wallet:admin_pricing')

        # 1. Update Financial Settings
        res_settings = self.client.post(url, {
            'action': 'save_financial_settings',
            'currency_code': 'USD',
            'currency_symbol': '$',
            'transfer_fee_coins': '5',
            'cashout_rate_per_coin': '0.75',
            'min_cashout_coins': '20',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res_settings.status_code, 200)

        sys_wallet = SystemWallet.get_instance()
        self.assertEqual(sys_wallet.currency_code, 'USD')
        self.assertEqual(sys_wallet.currency_symbol, '$')
        self.assertEqual(sys_wallet.transfer_fee_coins, 5)
        self.assertEqual(sys_wallet.cashout_rate_per_coin, Decimal('0.75'))
        self.assertEqual(sys_wallet.min_cashout_coins, 20)

        # 2. Create New Bundle
        res_create = self.client.post(url, {
            'action': 'create_bundle',
            'name': 'Dollar Exam Pack',
            'coins': '250',
            'price_zar': '19.99',
            'badge': 'BEST DEAL',
            'description': 'Full term exam pack in USD',
            'order': '10',
            'is_active': '1'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res_create.status_code, 200)

        bundle = CoinBundle.objects.get(name='Dollar Exam Pack')
        self.assertEqual(bundle.coins, 250)
        self.assertEqual(bundle.price_zar, Decimal('19.99'))
        self.assertEqual(bundle.badge, 'BEST DEAL')
        self.assertTrue(bundle.is_active)

        # 3. Save / Edit Bundle
        res_edit = self.client.post(url, {
            'action': 'save_bundle',
            'bundle_id': bundle.id,
            'name': 'Dollar Exam Pack Deluxe',
            'coins': '300',
            'price_zar': '24.99',
            'badge': 'UPDATED',
            'description': 'Updated description',
            'order': '5',
            'is_active': '1',
            'change_reason': 'Added bonus coins'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res_edit.status_code, 200)

        bundle.refresh_from_db()
        self.assertEqual(bundle.name, 'Dollar Exam Pack Deluxe')
        self.assertEqual(bundle.coins, 300)
        self.assertEqual(bundle.price_zar, Decimal('24.99'))

        # 4. Delete Bundle
        res_del = self.client.post(url, {
            'action': 'delete_bundle',
            'bundle_id': bundle.id
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res_del.status_code, 200)
        self.assertFalse(CoinBundle.objects.filter(id=bundle.id).exists())

    def test_sell_coins_view(self):
        """User sells coins and receives fiat cashout payout."""
        wallet = StudentWallet.objects.get(user=self.user)
        wallet.credit_coins(200)

        sys_wallet = SystemWallet.get_instance()
        sys_wallet.min_cashout_coins = 50
        sys_wallet.cashout_rate_per_coin = Decimal('0.80')
        sys_wallet.save()

        self.client.login(email='walletuser@example.com', password='Password123!')
        url = reverse('wallet:sell_coins')

        # GET view
        get_res = self.client.get(url)
        self.assertEqual(get_res.status_code, 200)
        self.assertContains(get_res, 'SELL STUDY COINS & REQUEST PAYOUT')

        # POST sell
        post_res = self.client.post(url, {
            'coins': 100,
            'payout_method': 'Standard Bank EFT',
            'account_holder': 'Student Name',
            'bank_name': 'Standard Bank',
            'account_number': '1234567890',
            'branch_code': '051001',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(post_res.status_code, 200)
        data = post_res.json()
        self.assertTrue(data['success'])

        wallet.refresh_from_db()
        self.assertEqual(wallet.coins, 100)  # 200 - 100

        # Verify transaction logged
        tx = CoinTransaction.objects.filter(wallet=wallet, transaction_type='COIN_SALE').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, -100)




