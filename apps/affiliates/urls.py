from django.urls import path

from . import views

app_name = "affiliates"

urlpatterns = [
    path("apply/", views.apply_view, name="apply"),
    path("status/", views.application_status_view, name="application_status"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("bank-details/", views.bank_details_view, name="bank_details"),

    # Phase 6 - referral tracking
    path("links/", views.my_links_view, name="my_links"),
    path("links/<uuid:product_id>/generate/", views.generate_link_view, name="generate_link"),

    # Phase 7 - commission calculations
    path("conversions/", views.my_conversions_view, name="my_conversions"),
]