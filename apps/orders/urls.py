from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout_view, name="checkout"),
    path("", views.order_list, name="order_list"),
    path("<str:reference>/", views.order_detail, name="order_detail"),
    path("<str:reference>/download/<uuid:item_id>/", views.download_product, name="download_product"),
]
