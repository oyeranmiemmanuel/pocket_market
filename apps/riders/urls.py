from django.urls import path

from . import views

app_name = "riders"

urlpatterns = [
    path("apply/", views.apply_view, name="apply"),
    path("status/", views.application_status_view, name="application_status"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("active-delivery/", views.active_delivery_view, name="active_delivery"),
    path("activity/", views.activity_view, name="activity"),
    path("availability/toggle/", views.toggle_availability_view, name="toggle_availability"),
    path("profile/", views.profile_view, name="profile"),
    path("earnings/", views.earnings_view, name="earnings"),
    path("bank-details/", views.bank_details_view, name="bank_details"),
]