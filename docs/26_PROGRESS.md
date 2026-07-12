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
guest and logged-in users via `<uuid:...>` URL routes. Has its own basic
template. Not yet linked from any product page (no "Add to Cart" button
exists anywhere yet).

## Exists but old / not yet integrated

**Checkout & payments** - still the *original* monolith flow: single-
product `buy_now`/`checkout` against Paystack, tied to `apps.Order`
(no line items). Sits alongside the new `cart` app with no bridge between
them yet.

**Admin dashboard** - original custom staff dashboard, untouched.

**Contact form** - `ContactMessage` model + view, untouched.

## Not started

`orders` (real multi-item order + line items - the actual bridge between
`cart` and a real checkout), `payments` (as its own app, vs. Paystack
calls embedded directly in monolith views), `delivery`, `notifications`,
`dashboard` (as its own app), `analytics`, `wishlist`, `api`.

## The honest gap

The bigger missing piece isn't routes/templates, it's that **cart and
checkout aren't connected to each other yet**. There are two parallel,
disconnected systems right now: the old single-product Paystack checkout,
and the new multi-item cart. Building `orders` properly (real `Order` +
`OrderItem` lines built from the cart, handed to `payments`) is real
model/design work, not just wiring up HTML.
