from django.apps import AppConfig


class MainConfig(AppConfig):
    """
    AppConfig for the original monolithic app package.

    This is being incrementally split into accounts/catalog/cart/orders/
    payments/delivery/notifications/dashboard/analytics/wishlist/api per
    docs/ARCHITECTURE.MD. Until that split is complete, this stays
    registered so the existing models/views/urls keep working.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps"