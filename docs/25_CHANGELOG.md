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

## Database

- `manage.py runserver` verified end-to-end multiple times across this
  work (not just `check`) - home, cart, register, and admin routes all
  respond correctly.
- See `03_DATABASE.md` for current setup steps and the app/model map.
