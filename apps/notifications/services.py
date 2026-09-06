"""
Creation helper for cross-user notifications. See models.py's module
docstring for why this exists separately from Django's `messages`
framework - short version: `messages` only reaches the user making the
current request, and several of these events (a webhook confirming
payment, a seller shipping an item, an admin approving an application)
happen in a request that belongs to someone else entirely, or no
request/user at all.
"""

from django.urls import reverse

from .models import Notification, NotificationCategory


def create_notification(*, user, category, message, url=""):
    """
    The one place a Notification row gets created. Every call site across
    the project (payments, delivery, sellers, affiliates) goes through
    this rather than calling Notification.objects.create directly, so
    there's a single spot to change later (e.g. if an email/push channel
    gets added on top of the in-app row).

    `user` may be None (e.g. a guest checkout with no account) - silently
    no-ops rather than raising, since there's nowhere for the
    notification to go.
    """
    if user is None:
        return None

    return Notification.objects.create(
        user=user,
        category=category,
        message=message,
        url=url,
    )


def notify_sellers_of_new_order(order):
    """
    One notification per distinct seller on the order, not one per line
    item - a seller who sold 3 items in one order should see "New order"
    once, not three times. Platform-owned items (OrderItem.seller is
    None) don't notify anyone here; there's no seller to tell.
    """
    seller_ids_seen = set()
    for item in order.items.select_related("seller__user").all():
        if item.seller_id is None or item.seller_id in seller_ids_seen:
            continue
        seller_ids_seen.add(item.seller_id)
        create_notification(
            user=item.seller.user,
            category=NotificationCategory.SELLER_NEW_ORDER,
            message=f"New order {order.reference} includes one of your products.",
            url=reverse("sellers:order_item_list"),
        )
