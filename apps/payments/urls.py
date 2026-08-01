from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("initiate/<str:order_reference>/", views.initiate_payment, name="initiate"),
    path("callback/", views.payment_callback, name="callback"),
    path("success/<str:order_reference>/", views.payment_success, name="success"),
    path("failed/<str:order_reference>/", views.payment_failed, name="failed"),
    path("webhook/", views.paystack_webhook, name="webhook"),
]
