# Changelog

Dates approximate to when the work was done in-session.

## Config / project skeleton

- Fixed `.gitignore.txt` -> `.gitignore` (git was never reading it, hence
  `.env` had ended up committed).
- Removed a leftover `import pymysql` that crashed Django on load (project
  uses PostgreSQL, not MySQL).
- Fixed `manage.py`, `config/wsgi.py`, `config/asgi.py`, `config/urls.py`
  after a series of folder renames (`store` -> `app` -> `apps`) left stale
  references at each step - including one point where the monolith's
  routes (home, checkout, admin dashboard) were dropped from
  `config/urls.py` entirely and had to be restored.
- Rewrote `config/settings.py`: secrets moved to `.env`, `INSTALLED_APPS`/
  `ROOT_URLCONF`/`WSGI_APPLICATION` fixed, added `PAYSTACK_SECRET_KEY`/
  `PAYSTACK_PUBLIC_KEY` (views.py referenced these but they didn't exist
  in settings anywhere).
- Added `.env.example`, `requirements/base.txt` + `development.txt` +
  `production.txt` (none existed before).
- Generated a real `SECRET_KEY` after finding the placeholder instruction
  text had been pasted into `.env` literally instead of a real key.

## Cleanup

- Deleted a leftover Django-tutorial `ToDolist`/`Item` model pair (broken
  `def str(self):` instead of `__str__`) and its form/view/route - unrelated
  to the ecommerce app.

## Accounts app

- Replaced Django's default `User` with a project-owned custom user
  (`accounts.User`), done before real data existed to avoid a mid-project
  swap. `UserProfile` kept as a separate one-to-one extension table.
- Built real `register_view`/`login_view`/`logout_view` + `RegisterForm`/
  `LoginForm` (previously empty stubs).
- Removed the old monolith's duplicate customer signup/login/logout
  (had mismatched form fields and referenced `User` with no import
  anywhere in the file).
- Fixed the admin email-verification flow (`verify_email`) redirecting to
  the wrong (customer, not admin) login/signup routes.

## Catalog app

- Added `Category` model.
- Moved `Product` out of the monolith into `catalog`, with auto-generated
  de-duplicating slugs.

## Cart app

- New: `Cart` (per-user or per-session) and `CartItem`, with add/update/
  remove tested end-to-end for both guest and logged-in users.
- Not yet wired into a real checkout - existing `buy_now`/`checkout` is
  still single-product against the old `Order` model.

## UUID + soft-delete retrofit

- Adopted `docs/06_UUID_POLICY.md` and the `deleted_at` soft-delete
  standard from `docs/03_DATABASE.md`.
- `core.BaseModel` rewritten: `id` is now `UUIDField(primary_key=True)`,
  `is_active` boolean replaced with `deleted_at` timestamp.
  `instance.delete()` soft-deletes by default (`hard=True` for real
  deletion), `instance.restore()` undoes it.
- `core.managers.ActiveManager`/`ActiveQuerySet` rewritten to filter on
  `deleted_at__isnull` instead of `is_active`.
- Every model retrofitted: `accounts.User`/`UserProfile`,
  `catalog.Category`/`Product`, `cart.Cart`/`CartItem`, and
  `apps.ContactMessage`/`Order` (the last two moved onto `BaseModel` for
  the first time in this pass, dropping their own duplicate
  `created_at`/`updated_at` declarations).
- `catalog.Product` kept its own explicit `is_active` field (merchant
  visibility toggle) since that's a different concept from soft-delete and
  the existing `ProductForm`/admin already depend on it being directly
  settable.
- All migrations wiped and regenerated project-wide (unavoidable - PK type
  changed on every model). Verified every model actually got a UUID `id`
  in its migration, not a stray integer `AutoField`.
- URL patterns updated from `<int:...>` to `<uuid:...>` converters
  wherever a model's pk is used in a route (`buy_now`, `checkout`,
  `delete_product`, and all of `cart`'s routes).
- Found and fixed a pre-existing bug while in there: `download_product`
  was referenced by a `redirect()` call but had no URL route registered at
  all - would have been a `NoReverseMatch` the moment anyone hit that path.
- `apps.ContactMessage.date_sent` was removed (superseded by
  `BaseModel.created_at`) - two `order_by('-date_sent')` call sites and one
  template reference (`templates/custom_admin/messages.html`) updated to
  `created_at` accordingly.
- Full retrofit verified live via `manage.py runserver` (not just
  `check`/test client): registration produces a UUID user id, product
  creation produces a UUID id, cart add/update work through the new
  `<uuid:...>` URL routes, and soft-delete/restore both behave correctly
  (`objects` still sees soft-deleted rows, `active` excludes them,
  `restore()` brings them back).

## Authentication (email verification + password reset)

- `register_view` now creates users with `is_active=False` and sends a
  verification email (custom `EmailVerificationTokenGenerator`, a
  `PasswordResetTokenGenerator` subclass whose hash includes `is_active`
  so a token auto-invalidates once used).
- New `verify_email` view activates the account and redirects to login.
- `login_view` now distinguishes "wrong password" from "correct password,
  unverified account" - previously both cases said "Invalid username or
  password", which would have confused anyone who signed up correctly but
  hadn't verified yet.
- Password reset wired up using Django's built-in `PasswordResetView`/
  `PasswordResetDoneView`/`PasswordResetConfirmView`/
  `PasswordResetCompleteView` with project-styled templates - no need to
  hand-roll this, Django's implementation is already solid.
- Verified live end-to-end in the sandbox: register -> account is inactive
  -> login correctly blocked with the right message -> verification email
  contains a working link -> visiting it activates the account -> login
  then succeeds. Same for password reset: request -> email sent -> token
  link -> new password set -> login with the new password works.

## Checkout, Orders, Payments, Inventory, Shipping

- New `orders` app: `Order`/`OrderItem`/`ShippingAddress` (real multi-item
  orders, snapshotted product name/price at purchase time). Distinct from
  the older single-product `apps.Order` still used by the legacy
  `buy_now`/`checkout` flow - not merged yet, see `28_DECISIONS.md`.
- New `payments` app: `Payment` model + Paystack integration
  (initialize/verify/webhook), same API pattern as the legacy monolith's
  Paystack code, generalized for multi-item orders. Both the browser
  callback and the server-to-server webhook confirm payment through the
  same idempotent `verify_payment()` function.
- Promoted `cart`'s private `_get_or_create_cart` helper to a public
  `apps.cart.services.get_or_create_cart`, since `orders` needed to read
  the cart too.
- Stock validated at checkout (blocks with a clear message if any cart
  line exceeds stock) and decremented only on confirmed payment - never
  at order-creation time, so an unpaid/abandoned order never holds stock
  hostage.
- Fixed a real bug found along the way: the legacy monolith's checkout
  views rendered from `payment/...` (singular - doesn't exist) instead of
  `payments/...` (plural - the real folder). Every hit to the old
  checkout flow was a hard `TemplateDoesNotExist` crash until this was
  fixed.
- Fixed a second real bug found *while testing this work*: cart clearing
  after successful payment used `.delete()`, which (per the UUID/soft-delete
  retrofit) soft-deletes rather than removing rows - so items were being
  marked deleted but still showing up via the default manager, meaning
  cart never actually emptied after a purchase. Changed to `.hard_delete()`.
  Caught by an actual end-to-end test, not by inspection.
- Added a "Proceed to Checkout" link to `cart_detail.html` (previously no
  path existed from the cart page to checkout).
- Rewrote `templates/payments/success.html`/`failed.html` (previously
  bare one-line placeholders) to show real order data.
- Verified fully end-to-end with mocked Paystack calls (real network
  calls to Paystack aren't reachable from this environment): full
  checkout -> payment -> stock decrement -> cart-clear chain; out-of-stock
  blocking at checkout; webhook signature verification (valid signature
  processes, invalid signature correctly rejected with 401); idempotency
  (verifying the same payment twice does not double-decrement stock).

## Shipping & Local Delivery (dual-method tracking)

- New `delivery` app: `Delivery` + `DeliveryUpdate`, built on the
  `DeliveryMethod`/`DeliveryStatus` enums that already existed in
  `core.enums` (predefined with exactly this "local delivery should feel
  faster/closer" intent - reused rather than duplicated).
- Local delivery and shipping each get their own stage progression
  (`LOCAL_DELIVERY_STAGES`/`SHIPPING_STAGES` in `apps.delivery.models`) -
  local delivery genuinely skips the shipping-only stages
  (`ready_for_shipping`/`shipped`/`in_transit`) rather than just being
  relabeled. `advance_stage()` rejects moving a delivery into a stage
  that doesn't belong to its method - tested live, confirmed it raises.
- `Order.delivery_method` added (chosen at checkout, read when the
  `Delivery` row is created after payment succeeds).
- Delivery fee and ETA both differ by method (`core.constants`:
  ₦1,000/~1 day local vs ₦2,500/~5 days shipping) - reinforces "faster
  and closer" through pricing/timing, not just wording.
- `apps.payments.services._finalize_successful_payment` now also creates
  the `Delivery` row (via `apps.delivery.services.create_delivery`) at
  the same point it marks the order paid and decrements stock.
- `DeliveryAdmin.save_model` routes stage edits through the validated
  `advance_stage()` service rather than a raw field write, so admin edits
  still produce a `DeliveryUpdate` history row.
- `orders/checkout.html` now has a delivery method radio choice with fee/ETA
  shown inline; `orders/order_detail.html` shows a live tracking widget
  (progress bar, current stage, ETA, courier/tracking info, full update
  history) - shown inline rather than as a separate tracking page.
- Verified end-to-end for both methods in one test run: correct stage
  sets, correct ETAs/fees, full local-delivery pipeline advancement
  (order_confirmed -> preparing -> out_for_delivery -> delivered,
  `Order.status` correctly flips to `delivered`), and template rendering
  for both.

## Full template/route audit - "create all necessary HTML" pass

Went through every URL pattern in the project and cross-referenced every
`render()` call against the actual templates directory, then tested every
route live (not just checked files exist) - as both anonymous, a regular
customer, and an admin user. Found and fixed several real, previously
undetected bugs:

- **`custom_admin/base.html` had no `{% block content %}` at all** - it
  hardcoded the dashboard's own content directly instead of delegating to
  a block. This meant every *other* admin page that extended it
  (`orders.html`, `users.html`, `messages.html`, `products.html`) had its
  real content silently discarded by Django's template inheritance, and
  instead showed the same generic dashboard shell regardless of which
  admin page was visited. Fixed by converting the hardcoded content into
  a real `{% block content %}`.
- **Six admin templates were missing `{% extends %}` entirely**
  (`add_product.html`, `delete_product.html`, `messages.html`,
  `orders.html`, `products.html`, `users.html`) - they had `{% block
  content %}` tags but no parent to inject into, so they rendered as bare
  content with no site chrome/sidebar/nav. All six fixed; for the four
  with a `<style>` preamble before their block tag, the block tag was
  moved to wrap the style block too (content outside blocks is silently
  dropped once `extends` is active, so leaving the style tag outside
  would have deleted all that page's CSS).
- **`products.html` additionally had broken template syntax**:
  `{% extend main/base.html %}` - wrong tag name (`extend` vs `extends`),
  no quotes around the path, and a nonexistent path. This alone would
  have raised a `TemplateSyntaxError` on every visit to the admin
  products page.
- **`core/base.html` used the wrong URL namespace separator** six times -
  `{% url 'accounts.login' %}` (dot) instead of `{% url 'accounts:login'
  %}` (colon). This crashed the site's actual homepage (`/`) with a
  `NoReverseMatch` for any anonymous visitor - about as severe as a bug
  gets.
- **Four customer-facing pages extended a `main/base.html` that never
  existed** (`services/branding.html`, `services/social.html`,
  `services/shop.html`, `products/clothing.html`) - `TemplateDoesNotExist`
  on every visit to `/branding/`, `/social/`, `/shop/`, `/clothing/`.
  Their block names already matched `core/base.html` (the real
  customer-facing layout) exactly, so just repointing the `extends` path
  fixed all four.
- **`password_verify` view had no URL route registered at all** (same
  pattern as the earlier `download_product` bug) - `/password-verify/`
  added.
- **Contact form was silently broken for everyone**: `admin_email =
  'nicholasereh@gmailcom'` (missing the dot before "com") in
  `contact_admin` - every submission raised inside `send_mail` and hit the
  generic `except Exception` handler, showing users a vague failure
  message no matter what they entered. Fixed the typo.
- New: `templates/main/contact.html`, `templates/password_verify.html` -
  didn't exist before.
- New: `edit_product` view + `admin-panel/products/edit/<uuid:pk>/` route
  + `custom_admin/edit_product.html` template - "update a product" had no
  implementation at all before this (only add and delete existed). Same
  `@login_required` + `@user_passes_test(is_admin)` protection as the
  other admin product views. Edit link added next to the existing Delete
  link in `products.html`.
- All of the above verified live, not just by reading code: every route
  hit as anonymous/customer/admin and checked for the right status code;
  admin routes confirmed to actually redirect non-staff users to login
  rather than just assuming the decorators work; full add -> edit ->
  delete product cycle run end-to-end including confirming the delete is
  a soft-delete (row survives, hidden from the `active` manager); dashboard
  and products pages confirmed to show their real content now instead of
  the previously-discarded version.

## Static file path collision (Django admin CSS not loading)

- `static/admin/css/base.css` (and 3 sibling files) turned out to be the
  site's *own* custom admin panel theme (Google Font import, custom
  layout classes) - but sitting at the exact path Django's real
  `django.contrib.admin` app uses for its own stylesheet
  (`admin/css/base.css`). Since `FileSystemFinder` (which checks
  `STATICFILES_DIRS`) runs before `AppDirectoriesFinder` in Django's
  default static file lookup order, this custom file completely shadowed
  Django's real admin CSS - every visit to `/admin/login/` (Django's
  built-in admin, not the site's custom one) loaded a stylesheet with
  none of the selectors it actually needed, so it rendered unstyled.
- Made worse by a second bug: `custom_admin/base.html` (the site's own
  admin panel layout) expects its stylesheet at `custom_admin/base.css` -
  a path that didn't exist at all, since the file was sitting under
  `admin/css/` instead. So the custom admin panel's own styling was
  *also* silently missing this whole time.
- Fixed by moving the files to where they were actually meant to be:
  `static/admin/css/base.css` -> `static/custom_admin/base.css` (the one
  file actually referenced by a template), plus `dark_mode.css`,
  `responsive.css`, `theme.js` moved alongside it (confirmed via search:
  none of these three are currently referenced by any template - moved
  for tidiness, not because anything was loading them).
- Verified via Django's static file finder directly (more reliable than
  the test client here, since `runserver`'s automatic static-serving URL
  injection isn't present when using the Django test client): confirmed
  `admin/css/base.css` now resolves to Django's real 23KB stylesheet
  (contains `.module`, no longer contains the custom theme's "Poppins"
  font import), and `custom_admin/base.css` now resolves to the moved
  custom theme file correctly.

## Real product browsing + Add to Cart + retiring the old checkout

- New `apps.catalog` views: `product_list` (with category filter) and
  `product_detail` (real "Add to Cart" form with quantity) - replaces
  the old monolith's `shop()` view, which linked every product straight
  to the single-product checkout being retired below.
- Two new templates (`catalog/product_list.html`,
  `catalog/product_detail.html`) matching the site's existing Tailwind +
  Font Awesome styling, wired under `/shop/`.
- **Retired the old single-product Paystack flow**: `buy_now`,
  `checkout`, `verify_payment`, `download_product`, `payment_success`,
  `paystack_webhook` removed from `apps/views.py` and their routes from
  `apps/urls.py`, per the decision to go cart-only. Confirmed live: all
  five old routes now correctly 404.
- Removed the templates that flow rendered, now orphaned:
  `services/shop.html`, `payments/checkout.html`,
  `payments/payment_success.html`, `payments/payment_success_physical.html`.
- Fixed 5 dead nav links in `core/base.html` (`{% url 'shop' %}` no
  longer existed) -> repointed to `{% url 'catalog:product_list' %}`.
- **Found and fixed a real security bug** while retiring the old flow:
  the old `download_product` view had **no ownership or payment check at
  all** - anyone who knew or guessed a product ID could download any
  digital file for free, whether they'd paid or not. The replacement
  (`apps.orders.views.download_product`, under
  `/orders/<reference>/download/<item_id>/`) requires the order belongs
  to the requesting user AND is actually paid AND the item belongs to
  that order. Verified live with an actual cross-user test: a second
  user attempting to download the first user's purchased file correctly
  gets a 404, not the file.
- Digital download link added to `order_detail.html`, shown only for
  paid orders with digital items.
- Full flow verified live end-to-end: browse `/shop/` -> product detail
  -> Add to Cart -> cart page -> checkout -> mocked Paystack payment ->
  order marked paid -> digital file downloads correctly -> cross-user
  download attempt correctly blocked.

## Admin signup email field bug

- `custom_signup.html` (the admin-panel signup template) rendered
  `{{ form.email }}`, but `signup_view` used Django's plain, unmodified
  `UserCreationForm` - which has no `email` field at all. Whatever the
  user typed into that box was silently dropped; `user.email` stayed
  blank; the verification email had nowhere real to go. This blocked the
  entire "create an admin, verify, log in via custom_login, add a
  product" flow at the very first step.
- Fixed with a new `AdminSignupForm` (`apps/forms.py`) - a proper
  `UserCreationForm` subclass with an actual `email = forms.EmailField()`,
  same pattern already used for the customer-facing `RegisterForm` in
  `apps.accounts.forms`.
- Verified live, full flow: signup (email correctly saved and verification
  email correctly sent to the real address) -> login blocked while
  unverified -> verification link activates the account -> login succeeds
  -> product successfully created via `/admin-panel/products/add/`.

## Redirect loop fix (ERR_TOO_MANY_REDIRECTS)

- `login_view` (`/custom_login/`) redirected *any* authenticated user
  straight to `admin_dashboard`, with no check that they were actually
  staff. `admin_dashboard` requires `is_admin` via `user_passes_test`,
  which (with no explicit `login_url`) redirects failures back to
  `settings.LOGIN_URL` = `custom_login`. Net effect: any authenticated
  but non-staff user (a regular customer account, for example) landing on
  `/custom_login/` bounced forever between the two - `custom_login` ->
  `admin_dashboard` -> `custom_login` -> ... - `ERR_TOO_MANY_REDIRECTS`.
- Fixed by checking `is_admin(request.user)` before auto-redirecting in
  `login_view`, not just `is_authenticated`.
- Verified live: a regular customer visiting `/custom_login/` now sees
  the login page normally (no loop); the same customer hitting
  `/admin-panel/` directly redirects exactly once to login (not
  infinitely); a real staff user visiting `/custom_login/` while already
  logged in still gets the intended convenience auto-redirect to the
  dashboard.

## Admin sidebar overlap + wrong login redirect on customer pages

- **Sidebar overlapping content**: `static/custom_admin/base.css` styled
  the content area with a bare `main{...}` element selector, but
  `custom_admin/base.html`'s actual markup uses `<div class="main-content">`
  - there's no `<main>` tag anywhere. That CSS rule (and its two responsive
  breakpoint versions) never matched anything, so the content div had no
  left margin at all and sat directly underneath the `position:fixed`
  sidebar. Fixed all three occurrences to target `.main-content` instead
  of `main`. Verified via the static file finder that the fixed selector
  is present and the old one is gone.
- **Checkout (and other customer pages) redirecting to the admin login**:
  `settings.LOGIN_URL = "custom_login"` is the *global* fallback Django's
  `@login_required` uses when no `login_url` is explicitly passed. That's
  correct for the actual admin views (they're paired with
  `@user_passes_test(is_admin)` and are meant to go to `custom_login`),
  but six genuinely customer-facing views were using bare `@login_required`
  and silently inheriting that admin default too:
  `apps.views.password_verify`, `apps.orders.views.checkout_view`/
  `order_list`/`order_detail`/`download_product`, and
  `apps.payments.views.initiate_payment`. Fixed by adding an explicit
  `login_url='accounts:login'` to each. Verified live: all six now
  correctly redirect anonymous visitors to `/accounts/login/`, while the
  real admin views (`/admin-panel/`, etc.) are unchanged and still
  correctly redirect to `/custom_login/`.

## Nav cart icon, AJAX add-to-cart, and guest checkout with merge-on-login

- New `apps.cart.context_processors.cart_context` - makes cart item
  count/items/total available on every page for the nav icon, without
  forcing a Cart/session to be created for visitors who've never touched
  the cart (only reads one if it already exists).
- Cart icon + dropdown popup added to `core/base.html`'s nav (badge only
  shows when count > 0), with "View Cart" link and live item list.
- `add_to_cart`/`update_cart_item`/`remove_from_cart` (cart app) and
  `product_detail`'s Add to Cart form (catalog app) now detect AJAX
  requests (`X-Requested-With: XMLHttpRequest`) and return a shared JSON
  shape (`apps.cart.services.cart_json_response`) instead of redirecting
  - clicking "Add to Cart" now stays on the product page and updates the
  nav icon/popup live via JS, rather than navigating to the cart page.
  Plain non-JS form submission still works as a fallback (redirects as
  before), so this is progressive enhancement, not a hard requirement.
- **Guest checkout flow**, matching the "browse/cart free, account
  required only at checkout" pattern common on major ecommerce sites:
  - Guests already could browse/add/remove/update/view cart with no
    login required (cart already supported session-based carts) -
    confirmed live, no changes needed there.
  - Checkout already required login (blocks guests) - confirmed.
  - `login_view` previously always redirected to `'home'` after login,
    ignoring any `?next=` - so a guest sent to login from checkout would
    land on the homepage instead of back at checkout. Fixed: reads
    `next` from GET/POST, validated via
    `django.utils.http.url_has_allowed_host_and_scheme` (never blindly
    trusts a URL param), redirects there after successful login.
  - `register_view` now preserves `next` through registration -> the
    "check your email" step -> the login link, so a guest who registers
    mid-checkout instead of logging in still ends up back at checkout
    after verifying and logging in.
  - **Cart merge on login**: new `apps.cart.services.merge_guest_cart_into_user`,
    called *before* `django.contrib.auth.login()` (must run first -
    `login()` cycles the session key, after which the guest cart's
    `session_key` would no longer match anything). Combines quantities
    per product rather than overwriting, in case the user's own account
    already had cart items from a previous session. Guest cart is hard-
    deleted after merging (soft-delete would leave its `session_key`
    occupying the unique constraint for no reason).
  - Verified live end-to-end: guest browses and adds two products (one
    of which the logging-in user already independently had 1 of in their
    own cart) -> guest hits checkout -> blocked, redirected to
    `/accounts/login/?next=/orders/checkout/` -> logs in -> lands back on
    `/orders/checkout/` (not home) -> merged cart correctly shows the
    guest-only item at its own quantity and the shared item's quantities
    correctly added together (1 + 3 = 4) -> old guest cart row confirmed
    actually gone afterward.

## Admin dashboard mobile responsiveness

- Previous mobile behavior (`@media(max-width:768px)`) made the sidebar
  `position:relative` and stacked it above the page content - meaning on
  a phone, a visitor had to scroll past the entire full-height nav list
  before reaching any actual dashboard content. Replaced with a proper
  slide-out overlay: sidebar stays `position:fixed` (its normal desktop
  behavior) but is translated off-screen (`transform:translateX(-100%)`)
  by default on mobile, with a hamburger toggle button (only visible
  ≤768px) and a semi-transparent backdrop that both open/close it. Tapping
  a nav link or the backdrop closes it automatically.
- Added a responsive-table rule (`table{ display:block; overflow-x:auto; }`
  at the same breakpoint) so the products/orders/users/messages admin
  tables scroll horizontally on narrow screens instead of squeezing
  columns unreadably or breaking the page layout.
- Added a `@media(max-width:480px)` tier for small phones specifically
  (tighter padding, smaller header text).
- Verified live: static file finder confirms all new CSS rules
  (`#admin-sidebar-toggle`, `#admin-sidebar-backdrop`, `aside.open`,
  responsive `table`) are present in the served stylesheet; all five
  admin pages (dashboard, products, orders, users, messages) render
  correctly with the toggle button and backdrop markup present - the fix
  is sitewide since they all extend the same `custom_admin/base.html`.

## Database

- `manage.py runserver` verified end-to-end multiple times across this
  work (not just `check`) - home, cart, register, and admin routes all
  respond correctly.
- See `03_DATABASE.md` for current setup steps and the app/model map.
