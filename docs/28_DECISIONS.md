# Decisions

Key architectural calls made along the way, and why, so they don't get
silently re-litigated or reversed by accident later.

## UUID primary keys everywhere

Per `06_UUID_POLICY.md`. Adopted after the project already had several
models built on integer `AutoField` pks - required a full migration wipe
and regeneration project-wide. Decided to do it now rather than later
since the DB was still empty/disposable; doing this retrofit after real
orders/payments data exists would be much more painful.

## Soft delete via `deleted_at`, not an `is_active` boolean

Per `03_DATABASE.md`. `core.BaseModel` previously used a boolean
`is_active` for this. Switched to a nullable `deleted_at` timestamp -
tells you *when* something was deleted, not just *whether*, and
`instance.delete()` now soft-deletes by default with `hard=True` as an
explicit escape hatch for real deletion.

## `Product.is_active` kept as its own field, separate from `deleted_at`

These mean different things: `deleted_at` is "this row was removed",
`is_active` on `Product` is "a merchant chose to hide this from sale
without deleting it." Collapsing them into one flag would lose that
distinction, and the existing `ProductForm`/admin already expose
`is_active` as a direct merchant-facing toggle.

## `UserProfile` kept separate from `User`, not merged

Considered merging profile fields (phone, country, avatar, bio) directly
into `User` for one less join. Decided against it - keeps the auth table
small and focused, and profile data can be filled in after signup rather
than being required upfront.

## Custom `User` model adopted before any real user data existed

Standard Django advice: swapping `AUTH_USER_MODEL` after real data and
foreign keys exist is a painful, risky migration. Since the project was
still early with a disposable DB, did the swap immediately rather than
deferring it.

## Cart supports both logged-in and guest users

`Cart` has a nullable `user` (OneToOne) *and* a nullable `session_key`,
with a `CheckConstraint` requiring at least one. Most of the site
currently forces login early (home page redirects anonymous users to
register), but cart was built to not hard-require that, in case that
changes.

## Migrations wiped and regenerated from scratch multiple times

Happened at least three separate times (accounts custom user swap,
`Product` moving from the monolith into `catalog`, and the UUID/soft-delete
retrofit). Each time was only safe because the database has stayed
empty/disposable throughout this phase - this is *not* the normal way to
evolve migrations once real data exists. See `03_DATABASE.md` for the
correct process (`makemigrations` incrementally) once the project has real
data to protect.

## Old single-product flow retired in favor of cart-only checkout (resolved)

Previously flagged as unresolved debt: the legacy monolith's
`buy_now`/`checkout` Paystack flow existed alongside the new
`orders`/`payments` apps. Decision made: retire the old flow entirely
rather than keep it as a "buy now" fast path - `buy_now`, `checkout`,
`verify_payment`, `download_product`, `payment_success`,
`paystack_webhook` all removed from `apps/views.py`/`apps/urls.py`.
Cart-based checkout (`apps.orders`/`apps.payments`) is now the only path
to purchase. Retiring it also surfaced a real security bug worth noting
for the record: the old `download_product` had no ownership or payment
check at all - the replacement in `apps.orders` checks both, verified
live with a cross-user test.

## Digital downloads live in `orders`, not `catalog` or `payments`

Considered attaching digital file delivery to `catalog.Product` directly
(since that's where `digital_file` lives) or to `payments` (since
delivery happens right after payment succeeds). Chose `orders` instead -
downloading is really about "does this specific paid order entitle this
specific user to this specific file," which is an order-ownership
question, not a product or payment question. The URL reflects that:
`/orders/<reference>/download/<item_id>/`, scoped to one order's items.

## Stock decremented at payment success, not at order creation

Considered decrementing stock as soon as an `Order`/`OrderItem` is
created (at checkout submission). Decided against it - an order isn't
real until it's paid, and reserving stock for unpaid/abandoned orders
would let someone block out inventory just by starting checkout and never
finishing. Tradeoff: no hard reservation during the checkout->payment
window, so two people can both pass stock validation for the last unit
and only the first to actually pay gets it (see `16_INVENTORY.md`'s
"known gap" section) - accepted as fine for now, revisit if it becomes a
real problem.
