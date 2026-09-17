"""
Chart datasets for the seller dashboard (spec section 5). Every function
here reads from real rows - SellerEarning / OrderItem - never returns
placeholder or estimated numbers. If a seller has no history yet, the
relevant series comes back empty and the template shows an empty state
instead of a blank chart.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone

from apps.core.enums import FulfillmentStatus


REVENUE_PERIODS = {
    "daily": {"trunc": TruncDate, "days": 30, "label_format": "%b %-d"},
    "weekly": {"trunc": TruncWeek, "days": 84, "label_format": "%b %-d"},   # ~12 weeks
    "monthly": {"trunc": TruncMonth, "days": 365, "label_format": "%b %Y"},  # ~12 months
}


def revenue_trend(profile, period="daily"):
    """
    Confirmed seller earnings (gross, non-reversed, non-cancelled) grouped
    by day/week/month. Returns {"labels": [...], "values": [...]} ready
    for Chart.js - both empty if the seller has no qualifying earnings in
    the window.
    """
    config = REVENUE_PERIODS.get(period, REVENUE_PERIODS["daily"])
    since = timezone.now() - timedelta(days=config["days"])

    rows = (
        profile.earnings
        .filter(reversal_of__isnull=True, created_at__gte=since)
        .exclude(status__in=["cancelled", "reversed"])
        .annotate(bucket=config["trunc"]("created_at"))
        .values("bucket")
        .annotate(total=Sum("order_amount"))
        .order_by("bucket")
    )

    labels = [row["bucket"].strftime(config["label_format"]) for row in rows]
    values = [float(row["total"] or Decimal("0")) for row in rows]
    return {"labels": labels, "values": values}


def orders_over_time(profile, days=30):
    """Distinct orders (not line items) containing this seller's products, per day, for the trailing window."""
    since = timezone.now() - timedelta(days=days)

    rows = (
        profile.order_items
        .filter(order__created_at__gte=since)
        .annotate(bucket=TruncDate("order__created_at"))
        .values("bucket")
        .annotate(total=Count("order_id", distinct=True))
        .order_by("bucket")
    )

    labels = [row["bucket"].strftime("%b %-d") for row in rows]
    values = [row["total"] for row in rows]
    return {"labels": labels, "values": values}


def orders_by_status(profile):
    """Line-item counts per FulfillmentStatus - always returns all statuses, zero-filled, so the legend stays stable."""
    counts = dict(
        profile.order_items.values("fulfillment_status")
        .annotate(total=Count("id"))
        .values_list("fulfillment_status", "total")
    )
    return {
        "labels": [label for _, label in FulfillmentStatus.choices],
        "values": [counts.get(value, 0) for value, _ in FulfillmentStatus.choices],
    }


def product_performance(profile, limit=5):
    """
    Top and bottom sellers by gross revenue, among products with at least
    one sale. A product with zero sales isn't "underperforming" - it just
    hasn't sold yet - so it's excluded from "lowest performing" rather
    than misleadingly shown at ₦0.
    """
    ranked = list(
        profile.order_items
        .values("product_id", "product_name")
        .annotate(
            revenue=Sum(
                ExpressionWrapper(F("unit_price") * F("quantity"), output_field=DecimalField(max_digits=14, decimal_places=2))
            ),
            units=Sum("quantity"),
        )
        .filter(revenue__gt=0)
        .order_by("-revenue")
    )

    top = ranked[:limit]
    bottom = list(reversed(ranked[-limit:])) if len(ranked) > limit else []

    return {
        "top": [{"name": r["product_name"], "revenue": float(r["revenue"]), "units": r["units"]} for r in top],
        "bottom": [{"name": r["product_name"], "revenue": float(r["revenue"]), "units": r["units"]} for r in bottom],
    }


def earnings_breakdown(profile):
    """Pending / Held / Available / Withdrawn, mapped onto the real EarningStatus lifecycle (see SellerProfile.pending_earnings for why PENDING and CONFIRMED are usually summed together elsewhere - here they're split out for the chart)."""
    return {
        "labels": ["Pending", "Held", "Available", "Withdrawn"],
        "values": [
            float(profile.pending_only_earnings),
            float(profile.held_earnings),
            float(profile.available_earnings),
            float(profile.paid_earnings),
        ],
    }
