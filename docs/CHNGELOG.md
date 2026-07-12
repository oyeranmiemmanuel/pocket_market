> **Superseded** - see the numbered docs (00_PROJECT_OVERVIEW.md onward) in this same folder, which are now the canonical guide. Kept here for history.

# Changelog

Dates approximate to when the work was done in-session, not necessarily
commit dates.

## Config / project skeleton

- Fixed `.gitignore.txt` -> `.gitignore` (git was never actually reading it,
  which is why `.env` had ended up committed).
- Removed a leftover `import pymysql` from `config/__init__.py` that crashed
  Django immediately (project uses PostgreSQL, not MySQL).
- Fixed `manage.py`, `config/wsgi.py`, `config/asgi.py` to point at
  `config.settings` (were still pointing at a pre-rename `toptech.settings`).
- Fixed `config/urls.py` to include the real app package's urls (had been
  pointing at a pre-rename `store.urls`, and at one point was missing the
  monolith's routes entirely - home page, checkout, admin dashboard, etc.
  were unreachable until this was restored).
- Rewrote `config/settings.py`: secrets moved out of source into `.env`,
  `INSTALLED_APPS`/`ROOT_URLCONF`/`WSGI_APPLICATION` fixed to match the
  actual `apps`/`config` folder layout, added `PAYSTACK_SECRET_KEY`/
  `PAYSTACK_PUBLIC_KEY` (views.py already expected these but they didn't
  exist anywhere in settings).
- Added `.env.example` and `requirements/base.txt` + `development.txt` +
  `production.txt` (none of these existed before).
- Fixed every app's `apps.py` so `AppConfig.name` matches its real dotted
  import path (`apps.<name>`, not a bare or stale name) - this bug recurred
  more than once across the project's history (`store` -> `app` -> `apps`
  renames each left some app configs stale).

## Cleanup

- Deleted a leftover Django-tutorial `ToDolist`/`Item` model pair (broken
  `def str(self):` instead of `__str__`, one method sitting outside its
  class entirely) along with its form, view, and url route - unrelated to
  the ecommerce app, dead weight.

## Accounts app

- Replaced Django's default `User` with a project-owned custom user
  (`accounts.User`, `AUTH_USER_MODEL = "accounts.User"`), done before any
  real data existed to avoid a painful mid-project swap.
- `UserProfile` kept as a separate one-to-one extension table (not merged
  into `User`) - phone, country, avatar, bio, etc.
- Built real `register_view` / `login_view` / `logout_view` (previously
  template-rendering stubs with no logic) and `RegisterForm` / `LoginForm`
  (previously empty).
- Removed the old monolith's duplicate, broken customer signup/login/logout
  (`SignupForm`/`LoginForm` had mismatched fields, `views.py` referenced
  `User` with no import anywhere in the file - a `NameError` waiting to
  happen).
- Fixed a pre-existing bug in the admin/staff email-verification flow
  (`verify_email`) - it was redirecting to the generic customer
  `login`/`signup` routes instead of the admin `custom_login`/
  `custom_signup` routes it always should have used.

## Catalog app

- Added `Category` model.
- Moved `Product` out of the monolith into `catalog`, on `core.BaseModel`,
  with auto-generated de-duplicating slugs.

## Cart app

- New: `Cart` (per-user or per-session, `CheckConstraint` requires one or
  the other) and `CartItem` (unique per cart+product), with `total_items`/
  `total_price` on `Cart` and `subtotal` on `CartItem`.
- Guest and logged-in flows both verified end-to-end (add / update quantity
  / remove), including quantity incrementing correctly when the same
  product is added twice.
- Not yet wired into a real checkout - the existing `buy_now`/`checkout`
  flow is still single-product and untouched; multi-item checkout against
  a real `Order` is `orders` app work.

## Database

- `manage.py runserver` verified working end-to-end (not just `check` /
  test client) - home, cart, register, and admin routes all respond
  correctly.
- Regenerated all migrations from scratch multiple times as models moved
  between apps (`Product`: monolith -> catalog; user model swap) - safe to
  do only because the local DB has stayed empty/disposable throughout this
  phase of development.
- See `DATABASE.md` for the current setup steps and the app/model map.