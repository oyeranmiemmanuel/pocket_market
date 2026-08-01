# Shipping & Local Delivery

`apps.delivery` - supports two distinct fulfillment methods, each with
its own tracking pipeline, not a relabeled shared one.

## Why two separate pipelines

Local delivery is deliberately not "shipping with fewer words." It skips
the shipping-only stages entirely rather than starting from something
like "ready to be shipped," which is a shipping-carrier concept that
doesn't apply when a rider is just bringing the order across town.

- **`SHIPPING_STAGES`** (7 stages): Order Confirmed -> Preparing ->
  Ready for Shipping -> Shipped -> In Transit -> Out for Delivery ->
  Delivered.
- **`LOCAL_DELIVERY_STAGES`** (4 stages): Order Confirmed -> Preparing
  Your Order -> On The Way (Arriving Soon) -> Delivered.

Both pull from the same underlying `core.enums.DeliveryStatus` (so
there's one canonical set of stage codes/labels project-wide), but each
method only progresses through its own subset -
`apps.delivery.services.advance_stage` rejects moving a local delivery
into a shipping-only stage (`ready_for_shipping`/`shipped`/`in_transit`)
or vice versa. Verified live: attempting this raises a clear error.

Local delivery also gets a shorter ETA (1 day vs 5) and a lower flat fee
(₦1,000 vs ₦2,500 - see `core.constants`), so the "this is the fast,
close option" impression comes from timing and price too, not just the
status wording.

## Models

- **`Delivery`** (one per `Order`, created automatically once payment
  succeeds - see `apps.payments.services`) - `method`, `current_stage`,
  `estimated_delivery_date`, plus method-specific optional fields:
  `tracking_number`/`carrier_name` (shipping) or
  `courier_name`/`courier_phone` (local delivery).
- **`DeliveryUpdate`** - one row per stage change, timestamped, with an
  optional note (e.g. "Rider is 10 minutes away"). This is what powers
  the tracking timeline on the order detail page - an accurate history,
  not just a single current status.

## Choosing a method

Selected by the customer at checkout (`orders.forms.CheckoutForm`,
`delivery_method` radio field), stored on `Order.delivery_method`, and
read when the `Delivery` row is created after payment. There's no
service-area check yet (e.g. blocking local delivery outside a city) -
any customer can pick either method regardless of address.

## Advancing a delivery (staff side)

`apps.delivery.services.advance_stage(delivery, new_stage, note="")` -
validates the stage belongs to this delivery's method (exception stages
`failed_delivery`/`cancelled` are always allowed for either), updates
`current_stage`, logs a `DeliveryUpdate`, and marks the `Order` as
`delivered` when the final stage is reached.

Wired into Django admin (`DeliveryAdmin.save_model`) so editing
`current_stage` there goes through the same validated path rather than a
raw field write - confirmed changes made in admin still produce a
`DeliveryUpdate` row.

No staff-facing dashboard view for this yet (Django admin only) - see
`20_ADMIN_PANEL.md`, still open.

## Customer-facing display

Shown inline on the order detail page (`templates/orders/order_detail.html`)
rather than a separate tracking page - progress bar, current stage,
ETA, courier/tracking info if set, and the full update timeline.
