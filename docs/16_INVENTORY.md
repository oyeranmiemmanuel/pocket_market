# Inventory

No separate inventory app yet - `stock` is a plain `PositiveIntegerField`
on `catalog.Product`. Enforcement lives in `orders`/`payments`:

- **At checkout** (`orders.services.checkout.validate_cart_stock`) -
  blocks checkout with a clear per-item message if any cart line exceeds
  current stock. Checked both when the checkout page is first shown and
  again on submit, since stock can change in between.
- **At payment confirmation** (`payments.services._finalize_successful_payment`) -
  stock is decremented only once payment actually succeeds, never at
  order-creation time. This means an abandoned/unpaid order never holds
  stock hostage - two people can have the same item in their cart
  simultaneously, and whoever pays first gets it.
- Decrement is floored at 0 (`max(0, stock - quantity)`) rather than
  allowed to go negative.

## Known gap

There's no reservation/locking between "checkout validated stock is OK"
and "payment actually succeeds" - if two people check out the last unit
at nearly the same moment, both could pass validation and one payment
would still succeed even though stock is now 0 (their `Order` would
still get created and paid; stock would go to 0 or -1 without the floor).
The `max(0, ...)` floor prevents negative stock, but doesn't prevent
overselling that one unit. Acceptable for now given order volume; revisit
if this becomes a real problem (would need `select_for_update()` around
the stock check + decrement, or a proper stock-reservation system).
