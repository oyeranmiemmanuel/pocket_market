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

## Not started

`orders` (real multi-item order + line items - the actual bridge between
`cart` and a real checkout), `payments` (as its own app, vs. Paystack
calls embedded directly in monolith views), `delivery`, `notifications`,
`dashboard` (as its own app), `analytics`, `wishlist`, `api`.

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
