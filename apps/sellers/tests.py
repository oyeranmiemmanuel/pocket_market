from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Product
from apps.core.enums import FulfillmentStatus
from apps.orders.models import Order, OrderItem

from .models import SellerProfile, SellerStatus

User = get_user_model()


def _make_seller(username, status=SellerStatus.APPROVED):
    user = User.objects.create_user(username=username, email=f"{username}@example.com", password="pass12345")
    profile = SellerProfile.objects.create(
        user=user,
        store_name=f"{username} store",
        store_slug=f"{username}-store",
        phone="08000000000",
        business_email=f"{username}@example.com",
        status=status,
    )
    return user, profile


class SellerProductManagementTests(TestCase):
    """
    Phase 4 - a seller must only ever be able to manage their OWN
    products. Access is enforced at the queryset/object level (not just
    hidden in the template), per section 41/42 of the implementation spec.
    """

    def setUp(self):
        self.seller_user, self.seller_profile = _make_seller("alice")
        self.other_user, self.other_profile = _make_seller("bob")

        self.own_product = Product.objects.create(
            seller=self.seller_profile, name="My Product", price=Decimal("1000.00"), stock=5,
        )
        self.other_product = Product.objects.create(
            seller=self.other_profile, name="Not Mine", price=Decimal("2000.00"), stock=5,
        )

        self.client.login(username="alice", password="pass12345")

    def test_seller_can_create_product_and_is_auto_assigned_as_owner(self):
        response = self.client.post(reverse("sellers:product_add"), {
            "name": "New Gadget",
            "description": "A gadget",
            "price": "5000.00",
            "product_type": "physical",
            "stock": "10",
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)

        product = Product.objects.get(name="New Gadget")
        self.assertEqual(product.seller_id, self.seller_profile.pk)

    def test_seller_can_edit_own_product(self):
        response = self.client.post(
            reverse("sellers:product_edit", args=[self.own_product.pk]),
            {
                "name": "Updated Name",
                "description": "updated",
                "price": "1500.00",
                "product_type": "physical",
                "stock": "3",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.own_product.refresh_from_db()
        self.assertEqual(self.own_product.name, "Updated Name")

    def test_seller_cannot_edit_another_sellers_product(self):
        response = self.client.post(
            reverse("sellers:product_edit", args=[self.other_product.pk]),
            {
                "name": "Hijacked",
                "description": "x",
                "price": "1.00",
                "product_type": "physical",
                "stock": "1",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 404)
        self.other_product.refresh_from_db()
        self.assertEqual(self.other_product.name, "Not Mine")

    def test_seller_cannot_delete_another_sellers_product(self):
        response = self.client.post(reverse("sellers:product_delete", args=[self.other_product.pk]))
        self.assertEqual(response.status_code, 404)
        self.other_product.refresh_from_db()
        self.assertFalse(self.other_product.is_deleted)

    def test_seller_can_soft_delete_own_product(self):
        response = self.client.post(reverse("sellers:product_delete", args=[self.own_product.pk]))
        self.assertEqual(response.status_code, 302)
        self.own_product.refresh_from_db()
        self.assertTrue(self.own_product.is_deleted)


class UnapprovedSellerAccessTests(TestCase):
    """A pending/rejected/suspended seller must not reach seller-only views."""

    def test_pending_seller_is_redirected_away_from_product_management(self):
        user, profile = _make_seller("pending_seller", status=SellerStatus.PENDING)
        self.client.login(username="pending_seller", password="pass12345")

        response = self.client.get(reverse("sellers:product_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("sellers:application_status"), response.url)

    def test_user_with_no_application_is_redirected_to_apply(self):
        user = User.objects.create_user(username="nobody", email="n@example.com", password="pass12345")
        self.client.login(username="nobody", password="pass12345")

        response = self.client.get(reverse("sellers:product_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("sellers:apply"), response.url)


class SellerOrderManagementTests(TestCase):
    """
    Phase 4 - a seller only ever sees the OrderItems belonging to them,
    never a full Order or another seller's line items from the same order.
    """

    def setUp(self):
        self.seller_user, self.seller_profile = _make_seller("carol")
        self.other_user, self.other_profile = _make_seller("dave")

        self.product_mine = Product.objects.create(
            seller=self.seller_profile, name="Mine", price=Decimal("1000.00"), stock=5,
        )
        self.product_theirs = Product.objects.create(
            seller=self.other_profile, name="Theirs", price=Decimal("2000.00"), stock=5,
        )

        buyer = User.objects.create_user(username="buyer2", email="buyer2@example.com", password="pass12345")
        self.order = Order.objects.create(
            user=buyer,
            reference="ORD-TEST-001",
            status="paid",
            email="buyer2@example.com",
            full_name="Buyer Two",
            phone="08099998888",
            subtotal=Decimal("3000.00"),
            total=Decimal("3000.00"),
        )
        self.item_mine = OrderItem.objects.create(
            order=self.order, product=self.product_mine, product_name="Mine",
            unit_price=Decimal("1000.00"), quantity=1, seller=self.seller_profile,
        )
        self.item_theirs = OrderItem.objects.create(
            order=self.order, product=self.product_theirs, product_name="Theirs",
            unit_price=Decimal("2000.00"), quantity=1, seller=self.other_profile,
        )

        self.client.login(username="carol", password="pass12345")

    def test_seller_only_sees_own_order_items(self):
        response = self.client.get(reverse("sellers:order_item_list"))
        self.assertContains(response, "Mine")
        self.assertNotContains(response, "Theirs")

    def test_seller_can_update_fulfillment_status_of_own_item(self):
        response = self.client.post(
            reverse("sellers:update_fulfillment_status", args=[self.item_mine.pk]),
            {"fulfillment_status": FulfillmentStatus.SHIPPED},
        )
        self.assertEqual(response.status_code, 302)
        self.item_mine.refresh_from_db()
        self.assertEqual(self.item_mine.fulfillment_status, FulfillmentStatus.SHIPPED)

    def test_seller_cannot_update_fulfillment_status_of_others_item(self):
        response = self.client.post(
            reverse("sellers:update_fulfillment_status", args=[self.item_theirs.pk]),
            {"fulfillment_status": FulfillmentStatus.SHIPPED},
        )
        self.assertEqual(response.status_code, 404)
        self.item_theirs.refresh_from_db()
        self.assertEqual(self.item_theirs.fulfillment_status, FulfillmentStatus.PENDING)
