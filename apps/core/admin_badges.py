"""
Shared colored status-badge rendering for Django admin list_display
columns. One small helper reused across every app's admin.py instead of
each admin.py hand-rolling its own HTML, so badge colors/shape stay
consistent everywhere (Sellers, Affiliates, Orders, Payments, Payouts).

Usage in an admin.py:

    from apps.core.admin_badges import status_badge

    @admin.register(Order)
    class OrderAdmin(admin.ModelAdmin):
        list_display = [..., "status_badge"]

        @admin.display(description="Status")
        def status_badge(self, obj):
            return status_badge(obj.get_status_display(), obj.status)
"""

from django.utils.html import format_html

# Maps a raw status value (the model field's value, not its display label)
# to a badge color. Every status string used anywhere in the project that
# has a "good/pending/bad" shape is listed here once, so a given word
# always renders the same color no matter which model it's on.
_BADGE_COLORS = {
    # positive / final-good states
    "approved": "green",
    "active": "green",
    "paid": "green",
    "delivered": "green",
    "shipped": "green",
    "success": "green",
    # neutral / in-progress states
    "pending": "yellow",
    "requested": "yellow",
    "processing": "yellow",
    "awaiting_payment": "yellow",
    "order_confirmed": "yellow",
    "preparing": "yellow",
    "ready_for_shipping": "yellow",
    "in_transit": "yellow",
    "out_for_delivery": "yellow",
    # negative / final-bad states
    "rejected": "red",
    "suspended": "red",
    "failed": "red",
    "cancelled": "red",
    "refunded": "red",
    "failed_delivery": "red",
}

_COLOR_STYLES = {
    "green": ("#f0fdf4", "#15803d"),
    "yellow": ("#fefce8", "#a16207"),
    "red": ("#fef2f2", "#b91c1c"),
    "gray": ("#f3f4f6", "#4b5563"),
}


def status_badge(label: str, raw_value: str):
    """
    Returns a small colored pill for use in a list_display column.
    `label` is what's shown (usually get_FOO_display()); `raw_value` is
    the underlying field value, used only to pick a color. Unrecognized
    values fall back to gray rather than guessing.
    """
    color = _BADGE_COLORS.get(raw_value, "gray")
    bg, fg = _COLOR_STYLES[color]
    return format_html(
        '<span style="background:{}; color:{}; padding:2px 10px; '
        'border-radius:999px; font-size:12px; font-weight:600;">{}</span>',
        bg, fg, label,
    )
