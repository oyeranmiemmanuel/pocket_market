# Orders

`apps.orders` - `Order`, `OrderItem`, `ShippingAddress`.

Note: this is distinct from the older `apps.Order` (single-product,
still used by the legacy `buy_now`/`checkout` flow in `apps/views.py`).
The two haven't been merged - see `28_DECISIONS.md`.

## Models

- **`Order`** - `reference` (unique, `ORD-...`), `status`
  (`pending`/`paid`/`shipped`/`delivered`/`cancelled`/`failed`),
  snapshotted `email`/`full_name`/`phone` (independent of the user's
  current profile), `subtotal`/`shipping_fee`/`total`.
- **`OrderItem`** - snapshotted `product_name`/`unit_price` at purchase
  time (so later product edits never rewrite order history), `quantity`,
  `subtotal` property.
- **`ShippingAddress`** - one-to-one with `Order`, captured at checkout.

All three on `core.BaseModel` (UUID pk, soft delete).

## Views

- `checkout_view` - see 13_CHECKOUT.md.
- `order_list` - a user's own orders (`/orders/`).
- `order_detail` - single order by reference, owner-only (`/orders/<reference>/`).

## Status lifecycle

`pending` (just created, unpaid) -> `paid` (payment confirmed, stock
decremented, cart cleared) -> `shipped`/`delivered` (not yet automated -
manual for now, no `delivery`/`shipping` app built yet) OR `failed`
(payment verification came back unsuccessful).
