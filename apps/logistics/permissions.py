"""
apps.logistics has no accounts of its own - a rider acting on a
PickupTask/DeliveryTask still needs an approved RiderProfile, and a
seller acting on a SellerFulfillment still needs an approved
SellerProfile. Rather than duplicating those two access checks here,
re-export the real ones from the apps that own those profiles.
"""

from apps.riders.permissions import approved_rider_required
from apps.sellers.permissions import approved_seller_required

__all__ = ["approved_rider_required", "approved_seller_required"]