from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.catalog.models import Product
from apps.orders.models import Order, OrderItem
from apps.sellers.models import SellerProfile, SellerStatus

from .models import AffiliateCommission, AffiliateProfile, AffiliateStatus, CommissionStatus
from .services import (
    calculate_order_item_allocation,
    record_conversion_for_order,
    resolve_affiliate_commission_rate,
    reverse_commission,
)

User = get_user_model()


class CommissionCalculationTests(TestCase):
    """
    Phase 7 - spec section 48's worked example, end to end:

        Product price = 50,000
        Platform commission = 10%
        Affiliate commission = 5%

        Expected: platform = 5,000, affiliate = 2,500, seller = 42,500

    then a refund/reversal, which must cancel the affiliate commission
    without deleting the original record.
    """

    def setUp(self):
        self.customer = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pass12345",
        )

        seller_user = User.objects.create_user(
            username="seller", email="seller@example.com", password="pass12345",
        )
        self.seller = SellerProfile.objects.create(
            user=seller_user,
            store_name="Seller Store",
            store_slug="seller-store",
            phone="08000000001",
            business_email="seller@example.com",
            status=SellerStatus.APPROVED,
            # No override -> platform default (10%, per core.constants).
        )

        affiliate_user = User.objects.create_user(
            username="affiliate", email="affiliate@example.com", password="pass12345",
        )
        self.affiliate = AffiliateProfile.objects.create(
            user=affiliate_user,
            affiliate_code="AFF-TEST0001",
            status=AffiliateStatus.ACTIVE,
            # No override -> platform default (5%, per core.constants).
        )

        self.product = Product.objects.create(
            seller=self.seller, name="Nike Shoes", price=Decimal("50000.00"), stock=10,
        )

        self.order = Order.objects.create(
            user=self.customer,
            reference="ORD-TEST0001",
            email="buyer@example.com",
            full_name="Buyer One",
            phone="08011112222",
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

    def test_commission_rate_hierarchy_falls_through_to_platform_default(self):
        rate = resolve_affiliate_commission_rate(product=self.product, affiliate=self.affiliate)
        self.assertEqual(rate, Decimal("5"))

    def test_commission_rate_hierarchy_prefers_product_override(self):
        self.product.affiliate_commission_rate = Decimal("10.00")
        self.product.save(update_fields=["affiliate_commission_rate"])

        rate = resolve_affiliate_commission_rate(product=self.product, affiliate=self.affiliate)
        self.assertEqual(rate, Decimal("10.00"))

    def test_commission_rate_hierarchy_prefers_affiliate_specific_rate_over_everything(self):
        self.product.affiliate_commission_rate = Decimal("10.00")
        self.product.save(update_fields=["affiliate_commission_rate"])
        self.affiliate.commission_rate = Decimal("20.00")
        self.affiliate.save(update_fields=["commission_rate"])

        rate = resolve_affiliate_commission_rate(product=self.product, affiliate=self.affiliate)
        self.assertEqual(rate, Decimal("20.00"))

    def test_order_item_allocation_matches_spec_worked_example(self):
        allocation = calculate_order_item_allocation(order_item=self.order_item, affiliate=self.affiliate)

        self.assertEqual(allocation["platform_amount"], Decimal("5000.00"))
        self.assertEqual(allocation["affiliate_amount"], Decimal("2500.00"))
        self.assertEqual(allocation["seller_amount"], Decimal("42500.00"))
        # The three splits must always fully account for the gross amount.
        self.assertEqual(
            allocation["platform_amount"] + allocation["affiliate_amount"] + allocation["seller_amount"],
            allocation["gross"],
        )

    def test_record_conversion_creates_pending_commission(self):
        created = record_conversion_for_order(self.order)

        self.assertEqual(len(created), 1)
        commission = AffiliateCommission.objects.get(order_item=self.order_item)
        self.assertEqual(commission.affiliate, self.affiliate)
        self.assertEqual(commission.commission_rate, Decimal("5"))
        self.assertEqual(commission.commission_amount, Decimal("2500.00"))
        self.assertEqual(commission.status, CommissionStatus.PENDING)

    def test_record_conversion_is_idempotent(self):
        """Calling this twice (e.g. callback + webhook both firing) must never create a second commission."""
        record_conversion_for_order(self.order)
        record_conversion_for_order(self.order)

        self.assertEqual(AffiliateCommission.objects.filter(order_item=self.order_item).count(), 1)

    def test_no_commission_without_an_attributed_affiliate(self):
        self.order.affiliate = None
        self.order.save(update_fields=["affiliate"])

        created = record_conversion_for_order(self.order)

        self.assertEqual(created, [])
        self.assertFalse(AffiliateCommission.objects.filter(order_item=self.order_item).exists())

    def test_suspended_affiliate_earns_nothing(self):
        self.affiliate.status = AffiliateStatus.SUSPENDED
        self.affiliate.save(update_fields=["status"])

        created = record_conversion_for_order(self.order)

        self.assertEqual(created, [])
        self.assertFalse(AffiliateCommission.objects.filter(order_item=self.order_item).exists())

    def test_self_referral_earns_nothing(self):
        """An affiliate must never earn a commission on their own purchase."""
        self.order.user = self.affiliate.user
        self.order.affiliate = self.affiliate
        self.order.save(update_fields=["user", "affiliate"])

        created = record_conversion_for_order(self.order)

        self.assertEqual(created, [])
        self.assertFalse(AffiliateCommission.objects.filter(order_item=self.order_item).exists())

    def test_refund_reverses_commission_without_deleting_the_original(self):
        record_conversion_for_order(self.order)
        commission = AffiliateCommission.objects.get(order_item=self.order_item, reversal_of__isnull=True)

        reversal = reverse_commission(commission=commission, reason="Order refunded.")
        commission.refresh_from_db()

        # Original preserved, just flipped to REVERSED - never deleted.
        self.assertEqual(commission.status, CommissionStatus.REVERSED)
        self.assertEqual(reversal.reversal_of, commission)
        self.assertEqual(reversal.commission_amount, -commission.commission_amount)

        # Reversed commissions must not count toward the affiliate's earnings anymore.
        self.affiliate.refresh_from_db()
        self.assertEqual(self.affiliate.total_earnings, Decimal("0.00"))