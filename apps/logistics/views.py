"""
Phase 2 - minimal seller/rider-facing views for the logistics boundary.

Deliberately simple. In particular, rider_pickup_task_list_view shows
every unassigned PickupTask to every approved rider (first to accept
gets it) - there is no service-area matching or dispatch algorithm yet.
That's future work; see apps.logistics.models module docstring.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.exceptions import ValidationFailedError
from apps.riders.permissions import approved_rider_required
from apps.sellers.permissions import approved_seller_required

from . import services
from .models import DeliveryTask, PickupTask, PickupTaskStatus, SellerFulfillment

# ---------------------------------------------------------------------------
# Seller-facing - mark a fulfillment ready for pickup.
# ---------------------------------------------------------------------------


@approved_seller_required
def seller_fulfillment_list_view(request):
    profile = request.user.seller_profile
    fulfillments = (
        SellerFulfillment.objects.filter(seller=profile)
        .select_related("order")
        .prefetch_related("packages")
        .order_by("-created_at")
    )
    return render(
        request,
        "logistics/seller_fulfillment_list.html",
        {"profile": profile, "fulfillments": fulfillments},
    )


@approved_seller_required
def mark_fulfillment_ready_view(request, pk):
    profile = request.user.seller_profile
    fulfillment = get_object_or_404(SellerFulfillment, pk=pk, seller=profile)

    if request.method == "POST":
        try:
            services.mark_fulfillment_ready(fulfillment)
            messages.success(request, "Marked ready for pickup.")
        except ValidationFailedError as exc:
            messages.error(request, str(exc))

    return redirect("logistics:seller_fulfillment_list")


# ---------------------------------------------------------------------------
# Rider-facing - view/accept pickup tasks and delivery tasks.
# ---------------------------------------------------------------------------


@approved_rider_required
def rider_pickup_task_list_view(request):
    profile = request.user.rider_profile

    available_tasks = (
        PickupTask.objects.filter(status=PickupTaskStatus.PENDING, rider__isnull=True)
        .select_related("package__fulfillment__order", "package__fulfillment__seller")
    )
    my_tasks = (
        PickupTask.objects.filter(rider=profile)
        .exclude(status=PickupTaskStatus.COLLECTED)
        .select_related("package__fulfillment__order", "package__fulfillment__seller")
    )

    return render(
        request,
        "logistics/rider_pickup_task_list.html",
        {"profile": profile, "available_tasks": available_tasks, "my_tasks": my_tasks},
    )


@approved_rider_required
def rider_accept_pickup_task_view(request, pk):
    profile = request.user.rider_profile
    task = get_object_or_404(PickupTask, pk=pk)

    if request.method == "POST":
        try:
            services.assign_rider_to_pickup_task(task, profile)
            messages.success(request, "Pickup task accepted.")
        except ValidationFailedError as exc:
            messages.error(request, str(exc))

    return redirect("logistics:rider_pickup_task_list")


@approved_rider_required
def rider_mark_collected_view(request, pk):
    profile = request.user.rider_profile
    task = get_object_or_404(PickupTask, pk=pk, rider=profile)

    if request.method == "POST":
        try:
            services.mark_package_collected(task)
            messages.success(request, "Package marked as collected.")
        except ValidationFailedError as exc:
            messages.error(request, str(exc))

    return redirect("logistics:rider_pickup_task_list")


@approved_rider_required
def rider_report_exception_view(request, pk):
    profile = request.user.rider_profile
    task = get_object_or_404(PickupTask, pk=pk, rider=profile)

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        missing = request.POST.get("missing") == "1"
        services.report_pickup_exception(task, missing=missing, reason=reason)
        messages.success(request, "Exception reported.")

    return redirect("logistics:rider_pickup_task_list")


@approved_rider_required
def rider_delivery_task_list_view(request):
    profile = request.user.rider_profile
    tasks = (
        DeliveryTask.objects.filter(rider=profile)
        .exclude(status="delivered")
        .select_related("delivery__order")
    )
    return render(
        request,
        "logistics/rider_delivery_task_list.html",
        {"profile": profile, "tasks": tasks},
    )


@approved_rider_required
def rider_mark_delivered_view(request, pk):
    profile = request.user.rider_profile
    task = get_object_or_404(DeliveryTask, pk=pk, rider=profile)

    if request.method == "POST":
        services.mark_delivery_task_delivered(task)
        messages.success(request, "Delivery marked as completed.")

    return redirect("logistics:rider_delivery_task_list")