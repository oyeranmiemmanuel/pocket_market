from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.core.exceptions import ValidationFailedError
from apps.logistics.models import DeliveryTask, DeliveryTaskStatus, PickupTask, PickupTaskStatus

from .forms import RiderApplicationForm, RiderBankDetailsForm, RiderProfileForm
from .permissions import approved_rider_required
from .services import apply_for_rider, deactivate_rider, set_rider_availability

_ACTIVE_PICKUP_STATUSES = (PickupTaskStatus.ASSIGNED, PickupTaskStatus.EN_ROUTE)
_ACTIVE_DELIVERY_STATUSES = (DeliveryTaskStatus.ASSIGNED, DeliveryTaskStatus.EN_ROUTE)
_TERMINAL_DELIVERY_STATUSES = (DeliveryTaskStatus.DELIVERED, DeliveryTaskStatus.FAILED, DeliveryTaskStatus.CANCELLED)


def _active_leg(profile):
    """
    The one job spec section 14 wants on the "Active Delivery" screen.
    A rider works two distinct leg types in this codebase - a PickupTask
    (collecting from a seller) and a DeliveryTask (the final leg to the
    buyer) - never coupled to each other by a direct FK, so whichever one
    this rider currently holds open is "the" active job. Delivery takes
    priority when a rider somehow has both open at once, since it's
    later in the journey and more time-sensitive.
    """
    delivery = (
        DeliveryTask.objects.filter(rider=profile, status__in=_ACTIVE_DELIVERY_STATUSES)
        .select_related("delivery__order__shipping_address")
        .order_by("-created_at")
        .first()
    )
    if delivery is not None:
        return "delivery", delivery

    pickup = (
        PickupTask.objects.filter(rider=profile, status__in=_ACTIVE_PICKUP_STATUSES)
        .select_related("package__fulfillment__seller", "package__fulfillment__order")
        .order_by("-created_at")
        .first()
    )
    if pickup is not None:
        return "pickup", pickup

    return None, None


@login_required(login_url="accounts:login")
def apply_view(request):
    existing = getattr(request.user, "rider_profile", None)
    if existing is not None:
        return redirect("riders:application_status")

    if request.method == "POST":
        form = RiderApplicationForm(request.POST)
        if form.is_valid():
            try:
                apply_for_rider(user=request.user, **form.cleaned_data)
            except ValidationFailedError as e:
                messages.error(request, str(e))
                return redirect("riders:apply")

            messages.success(request, "Application submitted! We'll review it shortly.")
            return redirect("riders:application_status")
    else:
        form = RiderApplicationForm()

    return render(request, "riders/apply.html", {"form": form})


@login_required(login_url="accounts:login")
def application_status_view(request):
    profile = getattr(request.user, "rider_profile", None)
    if profile is None:
        return redirect("riders:apply")

    return render(request, "riders/application_status.html", {"profile": profile})


@approved_rider_required
def dashboard_view(request):
    profile = request.user.rider_profile
    leg_type, active_task = _active_leg(profile)
    today = timezone.localdate()

    return render(request, "riders/dashboard.html", {
        "profile": profile,
        "leg_type": leg_type,
        "active_task": active_task,
        "completed_today": DeliveryTask.objects.filter(
            rider=profile, status=DeliveryTaskStatus.DELIVERED, delivered_at__date=today,
        ).count(),
        "total_completed": DeliveryTask.objects.filter(
            rider=profile, status=DeliveryTaskStatus.DELIVERED,
        ).count(),
        # RiderEarning now exists (spec sections 16/22-24) - real numbers,
        # from the same aggregate properties earnings_view/RiderProfile use.
        "earnings_available": True,
        "todays_earnings": profile.earnings.filter(
            reversal_of__isnull=True, created_at__date=today,
        ).aggregate(total=models.Sum("amount"))["total"] or 0,
        "available_balance": profile.available_earnings,
    })


@approved_rider_required
def toggle_availability_view(request):
    profile = request.user.rider_profile

    if request.method == "POST":
        try:
            set_rider_availability(profile=profile, available=not profile.is_available)
        except ValidationFailedError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, f"You are now {'available' if profile.is_available else 'unavailable'}.")

    return redirect("riders:dashboard")


@approved_rider_required
def active_delivery_view(request):
    """
    Spec section 14. Shows whichever leg (pickup or delivery) this rider
    currently holds open, a 4-step progression (Assigned / Picked Up /
    In Transit / Delivered), and ONLY the action(s) actually valid from
    its current state - never a status dropdown or free status switch.

    The actions themselves (mark collected, report exception, mark
    delivered) already exist as apps.logistics views/services; this page
    just surfaces them in context rather than duplicating that logic.
    """
    profile = request.user.rider_profile
    leg_type, task = _active_leg(profile)

    STEPS = ["Assigned", "Picked Up", "In Transit", "Delivered"]

    step_index = 0
    contact = None
    reference = None

    if leg_type == "pickup":
        fulfillment = task.package.fulfillment
        reference = fulfillment.order.reference
        contact = {"label": "Pickup from", "name": fulfillment.seller.store_name, "phone": fulfillment.seller.phone}
        step_index = 1 if task.status == PickupTaskStatus.COLLECTED else 0
    elif leg_type == "delivery":
        order = task.delivery.order
        reference = order.reference
        contact = {"label": "Deliver to", "name": order.full_name, "phone": order.phone}
        step_index = {
            DeliveryTaskStatus.ASSIGNED: 1,
            DeliveryTaskStatus.EN_ROUTE: 2,
            DeliveryTaskStatus.DELIVERED: 3,
        }.get(task.status, 1)

    return render(request, "riders/active_delivery.html", {
        "profile": profile,
        "leg_type": leg_type,
        "task": task,
        "reference": reference,
        "contact": contact,
        "steps": STEPS,
        "step_index": step_index,
    })


@approved_rider_required
def activity_view(request):
    """
    Spec section 17. Completed/failed/cancelled deliveries, paginated -
    never an unbounded historical dump. Earnings/payment history are
    intentionally NOT here yet: no rider earning ledger exists on the
    backend (see earnings_view), so showing a history list for money
    that was never actually tracked would be fabricating data.
    """
    profile = request.user.rider_profile

    tasks = (
        DeliveryTask.objects.filter(rider=profile, status__in=_TERMINAL_DELIVERY_STATUSES)
        .select_related("delivery__order")
        .order_by("-created_at")
    )

    status_filter = request.GET.get("status")
    if status_filter in DeliveryTaskStatus.values:
        tasks = tasks.filter(status=status_filter)

    paginator = Paginator(tasks, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "riders/activity.html", {
        "profile": profile,
        "page_obj": page_obj,
        "status_filter": status_filter,
    })


@approved_rider_required
def profile_view(request):
    profile = request.user.rider_profile

    if request.method == "POST":
        form = RiderProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("riders:profile")
    else:
        form = RiderProfileForm(instance=profile)

    return render(request, "riders/profile.html", {"form": form, "profile": profile})


@approved_rider_required
def earnings_view(request):
    """
    Spec sections 16/22-24. RiderEarning now exists (one row per
    completed pickup or delivery leg - see apps.riders.services.
    record_rider_earning, called from apps.logistics.services when a
    leg completes), so this is the same real, paginated, filterable
    transaction list as apps.sellers.views.earnings_view /
    apps.affiliates.views.my_conversions_view - never another rider's.
    """
    profile = request.user.rider_profile

    earnings = profile.earnings.filter(reversal_of__isnull=True).select_related("order").order_by("-created_at")

    status_filter = request.GET.get("status")
    if status_filter:
        earnings = earnings.filter(status=status_filter)

    paginator = Paginator(earnings, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "riders/earnings.html", {
        "profile": profile,
        "page_obj": page_obj,
        "status_filter": status_filter,
    })


@approved_rider_required
def bank_details_view(request):
    profile = request.user.rider_profile

    if request.method == "POST":
        form = RiderBankDetailsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Bank details updated.")
            return redirect("riders:dashboard")
    else:
        form = RiderBankDetailsForm(instance=profile)

    return render(request, "riders/bank_details.html", {"form": form})