from django.urls import path

from . import views

app_name = "logistics"

urlpatterns = [
    # Seller-facing
    path("sellers/fulfillments/", views.seller_fulfillment_list_view, name="seller_fulfillment_list"),
    path(
        "sellers/fulfillments/<uuid:pk>/mark-ready/",
        views.mark_fulfillment_ready_view,
        name="mark_fulfillment_ready",
    ),

    # Rider-facing - pickups
    path("riders/pickup-tasks/", views.rider_pickup_task_list_view, name="rider_pickup_task_list"),
    path(
        "riders/pickup-tasks/<uuid:pk>/accept/",
        views.rider_accept_pickup_task_view,
        name="rider_accept_pickup_task",
    ),
    path(
        "riders/pickup-tasks/<uuid:pk>/collected/",
        views.rider_mark_collected_view,
        name="rider_mark_collected",
    ),
    path(
        "riders/pickup-tasks/<uuid:pk>/exception/",
        views.rider_report_exception_view,
        name="rider_report_exception",
    ),

    # Rider-facing - deliveries
    path("riders/delivery-tasks/", views.rider_delivery_task_list_view, name="rider_delivery_task_list"),
    path(
        "riders/delivery-tasks/<uuid:pk>/delivered/",
        views.rider_mark_delivered_view,
        name="rider_mark_delivered",
    ),
]