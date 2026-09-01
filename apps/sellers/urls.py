from django.urls import path

from . import views

app_name = "sellers"

urlpatterns = [
    path("apply/", views.apply_view, name="apply"),
    path("status/", views.application_status_view, name="application_status"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("bank-details/", views.bank_details_view, name="bank_details"),

    # Phase 8 - earnings ledger
    path("earnings/", views.earnings_view, name="earnings"),

    # Phase 4 - product management
    path("products/", views.product_list_view, name="product_list"),
    path("products/add/", views.product_create_view, name="product_add"),
    path("products/<uuid:pk>/edit/", views.product_edit_view, name="product_edit"),
    path("products/<uuid:pk>/delete/", views.product_delete_view, name="product_delete"),

    # Phase 4 - order management
    path("orders/", views.order_item_list_view, name="order_item_list"),
    path("orders/<uuid:item_id>/update-status/", views.update_fulfillment_status_view, name="update_fulfillment_status"),
]