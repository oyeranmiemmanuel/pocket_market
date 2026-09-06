"""
Phase 12 (spec section 33) - platform-wide marketplace statistics for
staff. Lives here rather than in apps.core because apps.core isn't
registered in INSTALLED_APPS (it's a shared utility package, not a
Django app with models), so its admin.py would never be auto-
discovered. apps.ledger is the natural home anyway - these numbers are
fundamentally ledger-driven.
"""

from decimal import Decimal

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import F, Q, Sum, Count
from django.shortcuts import render

from apps.affiliates.models import (
    AffiliateClick, AffiliateCommission, AffiliatePayout, AffiliateProfile, AffiliateStatus,
)
from apps.core.enums import PayoutStatus
from apps.orders.models import Order, OrderItem, OrderStatus
from apps.sellers.models import SellerPayout, SellerProfile, SellerStatus

from .models import LedgerEntry, LedgerEntryType


@staff_member_required
def platform_analytics_view(request):
    ledger_totals = LedgerEntry.objects.aggregate(
        total_sales=Sum("gross_amount"),
        platform_revenue=Sum("platform_commission_amount"),
        seller_earnings=Sum("seller_earning_amount"),
        affiliate_commissions=Sum("affiliate_commission_amount"),
    )

    total_refunds = LedgerEntry.objects.filter(
        entry_type=LedgerEntryType.REFUND,
    ).aggregate(total=Sum("refund_amount"))["total"] or Decimal("0.00")

    pending_seller_payouts = SellerPayout.objects.filter(
        status__in=[PayoutStatus.PENDING, PayoutStatus.PROCESSING],
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    pending_affiliate_payouts = AffiliatePayout.objects.filter(
        status__in=[PayoutStatus.PENDING, PayoutStatus.PROCESSING],
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    overview = {
        "total_sales": ledger_totals["total_sales"] or Decimal("0.00"),
        "platform_revenue": ledger_totals["platform_revenue"] or Decimal("0.00"),
        "seller_earnings": ledger_totals["seller_earnings"] or Decimal("0.00"),
        "affiliate_commissions": ledger_totals["affiliate_commissions"] or Decimal("0.00"),
        "pending_seller_payouts": pending_seller_payouts,
        "pending_affiliate_payouts": pending_affiliate_payouts,
        "refunds": total_refunds,
        "num_sellers": SellerProfile.objects.filter(status=SellerStatus.APPROVED).count(),
        "num_affiliates": AffiliateProfile.objects.filter(status=AffiliateStatus.ACTIVE).count(),
        "num_orders": Order.objects.filter(
            status__in=[OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED],
        ).count(),
    }

    top_affiliates = AffiliateProfile.objects.annotate(
        total_commission=Sum(
            "commissions__commission_amount",
            filter=Q(commissions__reversal_of__isnull=True) & ~Q(commissions__status="cancelled"),
        ),
    ).filter(total_commission__gt=0).order_by("-total_commission")[:5]

    most_clicked_products = (
        AffiliateClick.objects.values("product__name")
        .annotate(clicks=Count("id"))
        .order_by("-clicks")[:5]
    )

    most_converted_products = (
        AffiliateCommission.objects.filter(reversal_of__isnull=True)
        .exclude(status="cancelled")
        .values("order_item__product__name")
        .annotate(conversions=Count("id"))
        .order_by("-conversions")[:5]
    )

    total_clicks = AffiliateClick.objects.count()
    total_conversions = AffiliateCommission.objects.filter(
        reversal_of__isnull=True,
    ).exclude(status="cancelled").count()
    overall_conversion_rate = round((total_conversions / total_clicks) * 100, 2) if total_clicks else Decimal("0.00")

    top_sellers = SellerProfile.objects.annotate(
        total_sold=Sum(
            "earnings__order_amount",
            filter=Q(earnings__reversal_of__isnull=True) & ~Q(earnings__status="cancelled"),
        ),
    ).filter(total_sold__gt=0).order_by("-total_sold")[:5]

    top_products = (
        OrderItem.objects.exclude(product__isnull=True)
        .values("product__name")
        .annotate(units_sold=Sum("quantity"), revenue=Sum(F("unit_price") * F("quantity")))
        .order_by("-units_sold")[:5]
    )

    order_volume = OrderItem.objects.count()

    context = {
        **admin.site.each_context(request),
        "title": "Platform Analytics",
        "overview": overview,
        "top_affiliates": top_affiliates,
        "most_clicked_products": most_clicked_products,
        "most_converted_products": most_converted_products,
        "total_clicks": total_clicks,
        "overall_conversion_rate": overall_conversion_rate,
        "top_sellers": top_sellers,
        "top_products": top_products,
        "order_volume": order_volume,
    }
    return render(request, "admin/ledger/analytics.html", context)