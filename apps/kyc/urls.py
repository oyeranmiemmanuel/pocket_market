from django.urls import path

from . import views

app_name = "kyc"

urlpatterns = [
    path("buyer/", views.buyer_kyc_view, name="buyer"),
    path("seller/", views.seller_kyc_view, name="seller"),
    path("affiliate/", views.affiliate_kyc_view, name="affiliate"),
    path("rider/", views.rider_kyc_view, name="rider"),
]