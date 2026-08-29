# Progress

Snapshot as of the UUID/soft-delete retrofit. See `25_CHANGELOG.md` for the
full history of how things got here.

## Done / verified working

**Foundation** - settings, `.env`, URLs, migrations, `AUTH_USER_MODEL`,
UUID primary keys + `deleted_at` soft delete across every model. Verified
via real `manage.py runserver` boots, not just `check`.

**`core`** - `BaseModel` (UUID pk, `created_at`/`updated_at`/`deleted_at`,
`active` manager, soft `delete()`/`restore()`), enums, validators,
exceptions, slug/reference-code utils.

**`accounts`** - custom `User` + separate `UserProfile`. Real signup,
login, logout, **email verification, and password reset** - all tested
live end-to-end (see 09_AUTHENTICATION.md, now fully implemented).
Accounts start inactive until the verification link is clicked. `role`
field exists (`UserRole` enum) but role-based permission *enforcement*
isn't built yet (see 10_AUTHORIZATION.md - still open).

Admin/staff side (separate from customer accounts - `custom_login`,
`signup_view` with email verification, `admin_dashboard`) still lives in
the original monolith `apps/views.py`, not yet its own app.

**`catalog`** - `Category` + `Product`, moved out of the monolith, with
slugs. No public browse/search/filter views yet - products are currently
only reachable through the *old* monolith's `shop`/`branding`/`social`/
`clothing` views.

**`cart`** - `Cart`/`CartItem`, add/update/remove tested live for both
guest and logged-in users via `<uuid:...>` URL routes. Now has a
"Proceed to Checkout" link into `orders`.

## Checkout / Orders / Payments / Inventory / Shipping - now built

**`orders`** - real multi-item `Order`/`OrderItem`/`ShippingAddress`,
built from the cart at checkout. `order_list`/`order_detail` for
customers to view their own orders.

**`payments`** - Paystack integration (`Payment` model, initialize/
verify/webhook), verified end-to-end with mocked Paystack responses:
checkout -> payment -> stock decrement -> cart clear, out-of-stock
blocking, webhook signature verification, and idempotent double-processing
all tested and working.

**Inventory** - enforced at checkout (blocks over-stock) and at payment
confirmation (decrements stock) - see `16_INVENTORY.md` for the known
race-condition gap (no row locking yet between stock-check and
stock-decrement under concurrent checkouts of the last unit).

**Shipping/Local Delivery** - both fully built, `delivery` app, each with
its own tracking pipeline (see `17_SHIPPING.md`). No service-area
restriction yet (any customer can pick local delivery regardless of
address), no staff dashboard for advancing stages beyond Django admin.

## Exists but old / not yet integrated

**Checkout & payments** - still the *original* monolith flow: single-
product `buy_now`/`checkout` against Paystack, tied to `apps.Order`
(no line items). Sits alongside the new `cart` app with no bridge between
them yet.

**Admin dashboard** - original custom staff dashboard. Had several
template-inheritance bugs that silently broke most of it (see
`25_CHANGELOG.md`'s "Full template/route audit" entry) - now fixed and
verified live: dashboard, orders, products, users, messages pages all
correctly show their real content. Product CRUD now complete - create,
edit (was entirely missing before), and delete (soft-delete) all working
and admin-only-protected.

**Contact form** - `ContactMessage` model + view, untouched.

## Not started (as of the Phase 3 seller-system snapshot)

At this point `orders`, `payments`, and `delivery` had already been built
(see "Checkout / Orders / Payments / Inventory / Shipping - now built"
above) - `dashboard` (as its own app), `analytics`, `wishlist`, `api`
were the remaining gaps. See "Not started" further below for what's still
open after Phase 4.

## The honest gap now

Cart, checkout, delivery tracking, and real product browsing are all
connected and reachable from normal navigation now. The old
single-product `buy_now`/`checkout` flow has been retired entirely -
cart-based checkout is the only path to purchase now. What's still
missing: no staff UI for advancing a delivery's stage beyond Django
admin; no customer-facing "estimated arrival countdown"; no push/email
notifications when a delivery stage changes (that's
`18_NOTIFICATIONS.md`, still open); no role-based permission enforcement
beyond `is_staff`/`is_superuser` (`10_AUTHORIZATION.md`, still open);
`clothing`/`branding`/`social` pages are still static (not tied to real
catalog browsing/filtering the way `/shop/` now is).

## Marketplace build - Phase 4 (multi-seller product/order architecture)

Per the marketplace/affiliate implementation spec's phased plan (Phase 3
was the seller application/approval system, already done - see above).

**Done** - `OrderItem` now carries `seller` (nullable FK, snapshotted at
checkout from `product.seller`), a frozen `platform_commission_rate`
snapshot, and its own `fulfillment_status` independent of `Order.status`.
One `Order` can span several sellers; each `OrderItem` correctly retains
whichever seller actually sold it (verified live with a cart containing
products from two different sellers plus a platform-owned product - see
`orders.tests.MultiSellerCheckoutTests`). Approved sellers now have real
product CRUD (`/sellers/products/`) scoped to their own products only,
and an order view (`/sellers/orders/`) scoped to their own `OrderItem`s
only, with fulfillment status they can update themselves - all with
object-level ownership checks (404, not a hidden link, for someone
else's product or order item), and fulfillment updates rejected
server-side for unpaid orders regardless of what the form submits. The
seller dashboard now shows real product/order/fulfillment counts.

**Not done yet (later phases)** - affiliate system (`AffiliateProfile`,
links, click tracking, attribution), commission calculations as their own
service layer, the internal financial ledger, seller/affiliate payouts,
and therefore no real seller earnings/pending-payout/available-balance
numbers yet (dashboard says so explicitly rather than showing fabricated
figures).

## Not started

Affiliate system, referral tracking, commission ledger, seller/affiliate
payouts, `notifications`, `analytics`, `wishlist`, `api`.
