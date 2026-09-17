from django.urls import path

from . import views

app_name = "logistics"

urlpatterns = [
    # Rider - pickup tasks
    path("pickup-tasks/", views.rider_pickup_task_list_view, name="rider_pickup_task_list"),
    path("pickup-tasks/<uuid:task_id>/accept/", views.rider_accept_pickup_task_view, name="rider_accept_pickup_task"),
    path("pickup-tasks/<uuid:task_id>/collected/", views.rider_mark_collected_view, name="rider_mark_collected"),
    path("pickup-tasks/<uuid:task_id>/exception/", views.rider_report_exception_view, name="rider_report_exception"),

    # Rider - delivery tasks
    path("delivery-tasks/", views.rider_delivery_task_list_view, name="rider_delivery_task_list"),
    path("delivery-tasks/<uuid:task_id>/delivered/", views.rider_mark_delivered_view, name="rider_mark_delivered"),

    # Seller - fulfillment / pickup readiness
    path("fulfillments/", views.seller_fulfillment_list_view, name="seller_fulfillment_list"),
    path("fulfillments/<uuid:fulfillment_id>/ready/", views.mark_fulfillment_ready_view, name="mark_fulfillment_ready"),
]