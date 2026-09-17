from django.contrib import messages
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.exceptions import ValidationFailedError

from apps.riders.permissions import approved_rider_required
from apps.sellers.permissions import approved_seller_required

from .models import (
    DeliveryTask,
    DeliveryTaskStatus,
    PickupTask,
    PickupTaskStatus,
    SellerFulfillment,
)
from .services import (
    assign_rider_to_pickup_task,
    mark_delivery_task_delivered,
    mark_fulfillment_ready,
    mark_package_collected,
    report_pickup_exception,
)


@approved_rider_required
def rider_pickup_task_list_view(request):
    profile = request.user.rider_profile

    my_tasks = (
        PickupTask.objects
        .filter(rider=profile, status__in=[
            PickupTaskStatus.ASSIGNED,
            PickupTaskStatus.EN_ROUTE,
        ])
        .select_related(
            "package__fulfillment__seller",
            "package__fulfillment__order",
        )
    )

    available_tasks = (
        PickupTask.objects
        .filter(status=PickupTaskStatus.PENDING, rider__isnull=True)
        .select_related(
            "package__fulfillment__seller",
            "package__fulfillment__order",
        )
    )

    return render(request, "logistics/rider_pickup_task_list.html", {
        "my_tasks": my_tasks,
        "available_tasks": available_tasks,
        "profile": profile,
    })


@approved_rider_required
@require_POST
def rider_accept_pickup_task_view(request, task_id):
    task = get_object_or_404(PickupTask, pk=task_id)

    try:
        assign_rider_to_pickup_task(task, request.user.rider_profile)
    except ValidationFailedError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Pickup task accepted.")

    return redirect("logistics:rider_pickup_task_list")


@approved_rider_required
@require_POST
def rider_mark_collected_view(request, task_id):
    task = get_object_or_404(
        PickupTask,
        pk=task_id,
        rider=request.user.rider_profile,
    )

    try:
        mark_package_collected(task)
    except ValidationFailedError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Package marked as collected.")

    return redirect("logistics:rider_pickup_task_list")


@approved_rider_required
@require_POST
def rider_report_exception_view(request, task_id):
    task = get_object_or_404(
        PickupTask,
        pk=task_id,
        rider=request.user.rider_profile,
    )

    reason = (request.POST.get("reason") or "").strip()
    if not reason:
        messages.error(request, "Please provide a reason for the exception.")
        return redirect("logistics:rider_pickup_task_list")

    missing = request.POST.get("missing") == "1"
    try:
        report_pickup_exception(task, missing=missing, reason=reason)
    except ValidationFailedError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Pickup exception reported.")

    return redirect("logistics:rider_pickup_task_list")


@approved_rider_required
def rider_delivery_task_list_view(request):
    profile = request.user.rider_profile
    tasks = (
        DeliveryTask.objects
        .filter(
            rider=profile,
            status__in=[
                DeliveryTaskStatus.ASSIGNED,
                DeliveryTaskStatus.EN_ROUTE,
            ],
        )
        .select_related("delivery__order")
        .order_by("-created_at")
    )

    return render(request, "logistics/rider_delivery_task_list.html", {
        "tasks": tasks,
        "profile": profile,
    })


@approved_rider_required
@require_POST
def rider_mark_delivered_view(request, task_id):
    task = get_object_or_404(
        DeliveryTask,
        pk=task_id,
        rider=request.user.rider_profile,
    )

    try:
        mark_delivery_task_delivered(task)
    except ValidationFailedError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Delivery marked as completed.")

    return redirect("logistics:rider_delivery_task_list")


@approved_seller_required
def seller_fulfillment_list_view(request):
    profile = request.user.seller_profile
    fulfillments = (
        SellerFulfillment.objects
        .filter(seller=profile)
        .select_related("order")
        .prefetch_related("packages")
        .order_by("-created_at")
    )

    return render(request, "logistics/seller_fulfillment_list.html", {
        "profile": profile,
        "fulfillments": fulfillments,
    })


@approved_seller_required
@require_POST
def mark_fulfillment_ready_view(request, fulfillment_id):
    fulfillment = get_object_or_404(
        SellerFulfillment,
        pk=fulfillment_id,
        seller=request.user.seller_profile,
    )

    try:
        mark_fulfillment_ready(fulfillment)
    except ValidationFailedError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Fulfillment marked ready for pickup.")

    return redirect("logistics:seller_fulfillment_list")
