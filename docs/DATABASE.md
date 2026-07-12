> **Superseded** - see the numbered docs (00_PROJECT_OVERVIEW.md onward) in this same folder, which are now the canonical guide. Kept here for history.

# Database Setup

## Engine

PostgreSQL, accessed via `psycopg2-binary`. Configured in `config/settings.py`,
values pulled from `.env` (see `.env.example` for the template).

## Local setup (one-time)

1. Install PostgreSQL locally if you haven't already.
2. Create the role and database used by this project. Connect as the
   Postgres superuser and run:

   ```sql
   CREATE USER database_admin WITH PASSWORD 'your-password-here';
   ALTER USER database_admin CREATEDB;
   CREATE DATABASE ecommerce_db OWNER database_admin;
   GRANT ALL PRIVILEGES ON DATABASE ecommerce_db TO database_admin;
   ```

   `CREATEDB` isn't required for the app itself, but it lets this role create
   the throwaway `test_ecommerce_db` Django spins up when you run tests.

3. Copy `.env.example` to `.env` and fill in real values:
   - `SECRET_KEY` - generate one with:
     ```
     python manage.py shell -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
     ```
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` - match whatever
     you used in step 2.

4. Install dependencies and migrate:
   ```
   pip install -r requirements/base.txt
   python manage.py migrate
   ```

## App / model map

Each app owns its own migrations under `apps/<app>/migrations/`. As of this
writing:

| App | Models | Notes |
|---|---|---|
| `apps` (monolith) | `ContactMessage`, `Order` | Original app; being split out per `ARCHITECTURE.MD`. `Order.user` points at `settings.AUTH_USER_MODEL`. |
| `accounts` | `User`, `UserProfile` | Custom user model (`AUTH_USER_MODEL = "accounts.User"`), set up before any real data existed to avoid a mid-project swap. `UserProfile` is a separate one-to-one extension table (phone, country, avatar, bio, etc.), not merged into `User`. |
| `catalog` | `Category`, `Product` | `Product` moved here from the old monolith. Both use auto-generated, de-duplicated slugs (`core.utils.unique_slugify`). |
| `cart` | `Cart`, `CartItem` | One cart per logged-in user (`OneToOneField`) or per anonymous session (`session_key`), enforced by a `CheckConstraint`. Not yet wired into a multi-item checkout - that's `orders` app territory. |
| `core` | *(no models registered as an app)* | Shared abstract `BaseModel` (`created_at`/`updated_at`/`is_active` + `active` manager), enums, validators, exceptions, slug/reference-code utils. Imported by other apps, not itself in `INSTALLED_APPS`. |

Apps not yet built: `orders`, `payments`, `delivery`, `notifications`,
`dashboard`, `analytics`, `wishlist`, `api` (see `ARCHITECTURE.MD` for the
intended responsibilities of each).

## Known gotchas already hit once - don't reintroduce these

- **AppConfig `name` must match the real dotted import path.** Every app
  lives under `apps/<name>/`, so `name = "apps.<name>"` in each `apps.py`,
  not just `"<name>"`.
- **`CheckConstraint` uses `condition=`, not `check=`,** on Django 6.x
  (the `cart` app's constraint hit this).
- If you ever see `InconsistentMigrationHistory`, it means the Postgres
  `django_migrations` bookkeeping table remembers an old migration history
  that no longer matches the files on disk. Since this project's DB has
  stayed disposable during early development, the fix each time has been to
  drop and recreate `ecommerce_db` and re-run `migrate` clean, rather than
  trying to patch the history in place.
- `AUTH_USER_MODEL` must be set (and the `accounts` app's own migrations
  must exist) *before* any other app's migrations reference it. If you ever
  need to change the user model again, plan a full migration wipe + DB
  drop/recreate rather than a live swap.

## Regenerating migrations from scratch (only when the DB is disposable)

```
# delete the numbered migration files (keep __init__.py) in whichever
# app(s) changed, e.g.:
rm apps/<app>/migrations/0*.py

python manage.py makemigrations
python manage.py migrate
```

Only do this when you're sure there's no real data to lose - check with
whoever's working on the project first if you're not sure.