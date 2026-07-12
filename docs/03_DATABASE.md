# Database Standards

- PostgreSQL
- UUID primary keys (see 06_UUID_POLICY.md)
- `created_at`, `updated_at`, `deleted_at` on every model (soft delete, not
  a boolean flag - see below)
- snake_case naming (Django's default column naming already does this)

## Shared base: `apps.core.models.BaseModel`

Every app's models inherit from this abstract base instead of
`models.Model` directly:

```python
id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
created_at = models.DateTimeField(auto_now_add=True)
updated_at = models.DateTimeField(auto_now=True)
deleted_at = models.DateTimeField(null=True, blank=True)
```

- `objects` (default manager) returns every row, including soft-deleted ones.
- `active` manager returns only rows where `deleted_at IS NULL`.
- `instance.delete()` soft-deletes (stamps `deleted_at`) by default.
  Pass `hard=True` to actually remove the row: `instance.delete(hard=True)`.
- `instance.restore()` clears `deleted_at`.
- `instance.is_deleted` property for quick checks.

Note: some models still keep their own separate `is_active` boolean where
that means something different from "this row was deleted" - e.g.
`catalog.Product.is_active` is a merchant-facing visibility toggle
(show/hide a product without deleting it), independent of `deleted_at`.
Don't confuse the two when reading model code.

## Local setup (one-time)

1. Install PostgreSQL locally if you haven't already.
2. Create the role and database:

   ```sql
   CREATE USER database_admin WITH PASSWORD 'your-password-here';
   ALTER USER database_admin CREATEDB;
   CREATE DATABASE ecommerce_db OWNER database_admin;
   GRANT ALL PRIVILEGES ON DATABASE ecommerce_db TO database_admin;
   ```

3. Copy `.env.example` to `.env`, fill in `SECRET_KEY` (generate with
   `python manage.py shell -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
   and the `DB_*` values matching step 2.

4. ```
   pip install -r requirements/base.txt
   python manage.py migrate
   ```

## App / model map

| App | Models | Notes |
|---|---|---|
| `apps` (monolith) | `ContactMessage`, `Order` | Original app, being split out per the roadmap. Both on `BaseModel` now (UUID pk + soft delete). |
| `accounts` | `User`, `UserProfile` | Custom user model (`AUTH_USER_MODEL = "accounts.User"`). `UserProfile` is a separate one-to-one extension (phone, country, avatar, bio), not merged into `User`. Has its own `role` field (`UserRole` enum) for authorization. |
| `catalog` | `Category`, `Product` | Auto-generated, de-duplicated slugs. `Product.is_active` is the merchant visibility toggle (distinct from soft-delete). |
| `cart` | `Cart`, `CartItem` | One cart per logged-in user or per anonymous session, enforced by a `CheckConstraint`. Not yet wired into a real checkout. |
| `core` | *(shared code, not itself an installed app)* | `BaseModel`, managers, enums, validators, exceptions, slug/reference-code utils. |

Not yet built: `orders`, `payments`, `delivery`, `notifications`,
`dashboard`, `analytics`, `wishlist`, `api`.

## Known gotchas - don't reintroduce these

- **AppConfig `name` must match the real dotted import path** (`apps.<name>`,
  not a bare or stale name). This bug recurred across multiple folder
  renames in this project's history.
- **`CheckConstraint` uses `condition=`, not `check=`** on Django 6.x.
- If URL patterns reference a model's pk, they must use `<uuid:...>`
  converters, not `<int:...>` - every model's pk is a UUID now.
- If you ever see `InconsistentMigrationHistory`, the Postgres
  `django_migrations` table remembers an old history that no longer
  matches the files on disk. While the DB stays disposable during early
  development, the fix has been to drop and recreate `ecommerce_db` and
  migrate clean, rather than patching history in place.

## Regenerating migrations from scratch (only when the DB is disposable)

```
rm apps/<app>/migrations/0*.py
python manage.py makemigrations
python manage.py migrate
```

Only do this when there's no real data to lose.
