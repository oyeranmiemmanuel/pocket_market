from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.affiliates.models import AffiliateCommission, AffiliateProfile, AffiliateStatus, CommissionStatus
from apps.catalog.models import Product
from apps.orders.models import Order, OrderItem
from apps.sellers.models import EarningStatus, SellerEarning, SellerProfile, SellerStatus

from .models import LedgerEntry, LedgerEntryType
from .services import process_order_financials, reverse_order_item_financials

User = get_user_model()


class FinancialLedgerTests(TestCase):
    """
    Spec section 48's worked example, end to end through the full Phase 8
    orchestrator:

        Product price = 50,000
        Platform commission = 10%
        Affiliate commission = 5%

        Expected: platform = 5,000, affiliate = 2,500, seller = 42,500

    then a refund, which must reverse the affiliate commission and the
    seller earning without deleting either original record, and the
    ledger must show both the original sale and the refund.
    """

    def setUp(self):
        self.customer = User.objects.create_user(
            username="buyer2", email="buyer2@example.com", password="pass12345",
        )

        seller_user = User.objects.create_user(
            username="seller2", email="seller2@example.com", password="pass12345",
        )
        self.seller = SellerProfile.objects.create(
            user=seller_user,
            store_name="Ledger Test Store",
            store_slug="ledger-test-store",
            phone="08000000002",
            business_email="seller2@example.com",
            status=SellerStatus.APPROVED,
        )

        affiliate_user = User.objects.create_user(
            username="affiliate2", email="affiliate2@example.com", password="pass12345",
        )
        self.affiliate = AffiliateProfile.objects.create(
            user=affiliate_user,
            affiliate_code="AFF-TEST0002",
            status=AffiliateStatus.ACTIVE,
        )

        self.product = Product.objects.create(
            seller=self.seller, name="Nike Shoes 2", price=Decimal("50000.00"), stock=10,
        )

        self.order = Order.objects.create(
            user=self.customer,
            reference="ORD-TEST0002",
            email="buyer2@example.com",
            full_name="Buyer Two",
            phone="08011112223",
            subtotal=Decimal("50000.00"),
            shipping_fee=Decimal("0.00"),
            total=Decimal("50000.00"),
            affiliate=self.affiliate,
            affiliate_code=self.affiliate.affiliate_code,
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=1,
            seller=self.seller,
            platform_commission_rate=Decimal("10"),
        )

    def test_worked_example_split_across_all_three_ledgers(self):
        process_order_financials(self.order)

        commission = AffiliateCommission.objects.get(order_item=self.order_item, reversal_of__isnull=True)
        self.assertEqual(commission.commission_amount, Decimal("2500.00"))

        earning = SellerEarning.objects.get(order_item=self.order_item, reversal_of__isnull=True)
        self.assertEqual(earning.platform_commission_amount, Decimal("5000.00"))
        self.assertEqual(earning.affiliate_commission_amount, Decimal("2500.00"))
        self.assertEqual(earning.earning_amount, Decimal("42500.00"))
        self.assertEqual(earning.status, EarningStatus.PENDING)

        entry = LedgerEntry.objects.get(order_item=self.order_item, entry_type=LedgerEntryType.SALE)
        self.assertEqual(entry.gross_amount, Decimal("50000.00"))
        self.assertEqual(entry.platform_commission_amount, Decimal("5000.00"))
        self.assertEqual(entry.seller_earning_amount, Decimal("42500.00"))
        self.assertEqual(entry.affiliate_commission_amount, Decimal("2500.00"))
        self.assertEqual(entry.net_payable_amount, Decimal("45000.00"))  # 42500 + 2500

        self.assertEqual(
            entry.platform_commission_amount + entry.seller_earning_amount + entry.affiliate_commission_amount,
            entry.gross_amount,
        )

    def test_process_order_financials_is_idempotent(self):
        process_order_financials(self.order)
        process_order_financials(self.order)

        self.assertEqual(SellerEarning.objects.filter(order_item=self.order_item).count(), 1)
        self.assertEqual(LedgerEntry.objects.filter(order_item=self.order_item, entry_type=LedgerEntryType.SALE).count(), 1)
        self.assertEqual(AffiliateCommission.objects.filter(order_item=self.order_item).count(), 1)

    def test_refund_reverses_affiliate_and_seller_without_deleting_originals(self):
        process_order_financials(self.order)

        commission = AffiliateCommission.objects.get(order_item=self.order_item, reversal_of__isnull=True)
        earning = SellerEarning.objects.get(order_item=self.order_item, reversal_of__isnull=True)

        refund_entry = reverse_order_item_financials(order_item=self.order_item, reason="Customer refund.")

        commission.refresh_from_db()
        earning.refresh_from_db()

        self.assertEqual(commission.status, CommissionStatus.REVERSED)
        self.assertEqual(earning.status, EarningStatus.REVERSED)

        self.assertTrue(
            AffiliateCommission.objects.filter(reversal_of=commission, commission_amount=Decimal("-2500.00")).exists()
        )
        self.assertTrue(
            SellerEarning.objects.filter(reversal_of=earning, earning_amount=Decimal("-42500.00")).exists()
        )

        self.assertEqual(refund_entry.entry_type, LedgerEntryType.REFUND)
        self.assertEqual(refund_entry.gross_amount, Decimal("-50000.00"))
        self.assertEqual(refund_entry.refund_amount, Decimal("50000.00"))
        self.assertEqual(LedgerEntry.objects.filter(order_item=self.order_item).count(), 2)

        self.affiliate.refresh_from_db()
        self.seller.refresh_from_db()
        self.assertEqual(self.affiliate.total_earnings, Decimal("0.00"))
        self.assertEqual(self.seller.total_earnings, Decimal("0.00"))
        self.assertEqual(self.seller.refunded_amount, Decimal("50000.00"))

    def test_reversing_twice_is_idempotent(self):
        process_order_financials(self.order)
        first = reverse_order_item_financials(order_item=self.order_item, reason="Refund.")
        second = reverse_order_item_financials(order_item=self.order_item, reason="Refund again?")

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(LedgerEntry.objects.filter(order_item=self.order_item).count(), 2)