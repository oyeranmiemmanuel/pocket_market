from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Product
from apps.core.enums import FulfillmentStatus
from apps.sellers.models import SellerProfile, SellerStatus

from .models import OrderItem
from .services import create_order_from_cart

User = get_user_model()


class MultiSellerCheckoutTests(TestCase):
    """
    Phase 4 - a single checkout must correctly split ownership across
    OrderItems when the cart contains products from different sellers
    (and platform-owned products with no seller at all).
    """

    def setUp(self):
        self.customer = User.objects.create_user(
            username="buyer", email="buyer@example.com", password="pass12345"
        )

        seller_a_user = User.objects.create_user(
            username="seller_a", email="a@example.com", password="pass12345"
        )
        self.seller_a = SellerProfile.objects.create(
            user=seller_a_user,
            store_name="Seller A Store",
            store_slug="seller-a-store",
            phone="08000000001",
            business_email="a@example.com",
            status=SellerStatus.APPROVED,
            commission_rate=Decimal("7.00"),
        )

        seller_b_user = User.objects.create_user(
            username="seller_b", email="b@example.com", password="pass12345"
        )
        self.seller_b = SellerProfile.objects.create(
            user=seller_b_user,
            store_name="Seller B Store",
            store_slug="seller-b-store",
            phone="08000000002",
            business_email="b@example.com",
            status=SellerStatus.APPROVED,
            # No override -> falls through to platform default (10%).
        )

        self.product_a = Product.objects.create(
            seller=self.seller_a, name="Nike Shoes", price=Decimal("50000.00"), stock=10,
        )
        self.product_b = Product.objects.create(
            seller=self.seller_b, name="Hoodie", price=Decimal("30000.00"), stock=10,
        )
        self.product_platform = Product.objects.create(
            seller=None, name="Platform Gadget", price=Decimal("20000.00"), stock=10,
        )

        self.cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=self.cart, product=self.product_a, quantity=1)
        CartItem.objects.create(cart=self.cart, product=self.product_b, quantity=1)
        CartItem.objects.create(cart=self.cart, product=self.product_platform, quantity=1)

    def _shipping_data(self):
        return {
            "address_line1": "1 Test Street",
            "city": "Ibadan",
            "state": "Oyo",
            "postal_code": "200001",
            "country": "Nigeria",
        }

    def test_order_items_retain_correct_seller_ownership(self):
        order = create_order_from_cart(
            user=self.customer,
            cart=self.cart,
            email="buyer@example.com",
            full_name="Buyer One",
            phone="08011112222",
            delivery_method="shipping",
            shipping_data=self._shipping_data(),
        )

        items_by_product = {item.product_id: item for item in order.items.all()}

        item_a = items_by_product[self.product_a.pk]
        item_b = items_by_product[self.product_b.pk]
        item_platform = items_by_product[self.product_platform.pk]

        self.assertEqual(item_a.seller_id, self.seller_a.pk)
        self.assertEqual(item_a.platform_commission_rate, Decimal("7.00"))

        self.assertEqual(item_b.seller_id, self.seller_b.pk)
        self.assertEqual(item_b.platform_commission_rate, Decimal("10"))  # platform default

        self.assertIsNone(item_platform.seller_id)
        self.assertEqual(item_platform.platform_commission_rate, Decimal("100"))

        # New line items always start out awaiting fulfillment.
        self.assertEqual(item_a.fulfillment_status, FulfillmentStatus.PENDING)

    def test_one_order_but_multiple_sellers(self):
        order = create_order_from_cart(
            user=self.customer,
            cart=self.cart,
            email="buyer@example.com",
            full_name="Buyer One",
            phone="08011112222",
            delivery_method="shipping",
            shipping_data=self._shipping_data(),
        )

        # Still exactly one customer-facing Order...
        self.assertEqual(order.items.count(), 3)
        # ...but three distinct sellers represented across its items.
        sellers_represented = set(OrderItem.objects.filter(order=order).values_list("seller_id", flat=True))
        self.assertEqual(sellers_represented, {self.seller_a.pk, self.seller_b.pk, None})

    def test_a_later_rate_change_does_not_rewrite_past_orders(self):
        order = create_order_from_cart(
            user=self.customer,
            cart=self.cart,
            email="buyer@example.com",
            full_name="Buyer One",
            phone="08011112222",
            delivery_method="shipping",
            shipping_data=self._shipping_data(),
        )

        item_a = order.items.get(product=self.product_a)
        original_rate = item_a.platform_commission_rate

        self.seller_a.commission_rate = Decimal("50.00")
        self.seller_a.save(update_fields=["commission_rate"])

        item_a.refresh_from_db()
        self.assertEqual(item_a.platform_commission_rate, original_rate)
