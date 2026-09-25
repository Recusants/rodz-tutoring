from django.test import TestCase
from accounts.models import CustomUser
from wallet.models import StudentWallet, CoinTransaction


class WalletTestCase(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='walletuser@example.com',
            password='Password123!'
        )

    def test_auto_created_wallet(self):
        wallet = StudentWallet.objects.get(user=self.user)
        self.assertEqual(wallet.coins, 0)

    def test_credit_and_debit_coins(self):
        wallet = StudentWallet.objects.get(user=self.user)
        # Credit 100 coins
        wallet.credit_coins(100, description="WhatsApp Payment Pack")
        self.assertEqual(wallet.coins, 100)
        self.assertEqual(CoinTransaction.objects.filter(wallet=wallet).count(), 1)

        # Debit 40 coins
        wallet.debit_coins(40, description="Unlocked Maths Pack")
        self.assertEqual(wallet.coins, 60)
        self.assertEqual(CoinTransaction.objects.filter(wallet=wallet).count(), 2)

    def test_cannot_overdraw(self):
        wallet = StudentWallet.objects.get(user=self.user)
        wallet.credit_coins(30)
        with self.assertRaises(ValueError):
            wallet.debit_coins(50)
