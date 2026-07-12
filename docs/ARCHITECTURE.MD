> **Superseded** - see the numbered docs (00_PROJECT_OVERVIEW.md onward) in this same folder, which are now the canonical guide. Kept here for history.

# NICO_APP Architecture Guide

Version: 1.0
Status: Planning / Refactoring
Database: PostgreSQL
Framework: Django
Python Version: 3.13+

---

# Project Goal

Build a scalable e-commerce platform that supports:

- Physical products
- Digital services
- Dispatch delivery
- Online payments
- Customer dashboard
- Admin dashboard
- Analytics
- Wishlist
- Notifications

The architecture should follow clean software engineering principles and be maintainable for long-term development.

---

# Current Refactoring Status

## Completed

- PostgreSQL configured
- Django connected to PostgreSQL
- Project cloned
- Initial apps separated
- Payment (Paystack) already exists
- Delivery app added
- Cart app added
- Orders app added

---

# Required Folder Structure

```
NICO_APP/

├── apps/
│
├── config/
│
├── docs/
│
├── media/
│
├── static/
│
├── templates/
│
├── requirements/
│
├── .env
├── .env.example
├── README.md
├── manage.py
└── .gitignore
```

---

# Apps

Current architecture should become:

```
apps/

accounts/
analytics/
api/
cart/
catalog/
core/
dashboard/
delivery/
notifications/
orders/
payments/
wishlist/
```

---

# Required Refactoring

## 1. Rename

❌ shop

↓

✅ catalog

Reason:

The app is no longer just a shop.

It manages:

- Products
- Categories
- Services
- Images
- Search

---

## 2. Merge

Merge:

digital/

↓

catalog/

Reason:

Products and Services belong to one catalog.

Inheritance will be used instead.

```
Item

├── Product

└── Service
```

---

## 3. Orders

Checkout logic should live inside:

```
orders/
```

instead of having a dedicated checkout app.

Orders app responsibilities:

- Checkout
- Orders
- Order Items
- Address
- Delivery Reference

---

## 4. Delivery

Use:

```
delivery/
```

instead of shipping.

Reason:

Business delivers using dispatch riders.

No shipping carriers.

Delivery should support:

- Rider Assignment
- Tracking
- Status History
- Delivery Fee
- Estimated Delivery
- Delivery Confirmation

---

## 5. Payments

Keep existing Paystack implementation.

Refactor to support multiple gateways.

Future gateways:

- Paystack
- Stripe

Payment module should expose one interface only.

Application should never directly call Paystack APIs.

---

# Folder Standards

Each business app should gradually evolve into:

```
catalog/

admin.py
apps.py
urls.py

models/
views/
services/
managers/

tests/
```

Large files should be split.

Avoid:

```
models.py
```

with hundreds of lines.

---

# Core Responsibilities

The Core app contains reusable infrastructure.

Eventually it should contain:

```
core/

models.py
managers.py
validators.py
constants.py
enums.py
exceptions.py
permissions.py
middleware.py
mixins.py

utils/
```

---

# Global Folder Responsibilities

templates/

Global HTML templates.

Example:

- base.html
- errors
- authentication layout

---

static/

Shared:

- CSS
- JavaScript
- Images

---

media/

User uploads.

Examples:

- Product Images
- User Profile Images

---

docs/

Project documentation.

Examples:

- Architecture
- API
- Deployment
- Database
- Authentication

---

requirements/

Instead of one requirements.txt

Use:

```
requirements/

base.txt

development.txt

production.txt
```

---

# Development Order

Phase 1

- Core
- Accounts

Phase 2

- Catalog

Phase 3

- Cart

Phase 4

- Orders

Phase 5

- Payments

Phase 6

- Delivery

Phase 7

- Notifications

Phase 8

- Dashboard

Phase 9

- Analytics

---

# Technical Guidelines

Business logic belongs in Services.

Views should remain thin.

Models should only define data.

Avoid business logic inside:

- views.py
- admin.py
- signals.py

Signals should only be used for cross-cutting concerns.

---

# Team Conventions

Every developer should:

✅ Use Services for business logic.

✅ Keep views small.

✅ Use PostgreSQL.

✅ Write reusable code.

❌ Do not duplicate logic.

❌ Do not directly couple apps together.

❌ Do not place business logic inside templates.

---

# Pending Tasks

- [ ] Convert config/settings.py into settings package
- [ ] Create BaseModel
- [ ] Create Custom User model
- [ ] Refactor Paystack
- [ ] Merge Digital into Catalog
- [ ] Build Delivery Tracking
- [ ] Implement Stripe
- [ ] Build Analytics
- [ ] Implement Celery
- [ ] Docker Deployment

---

Last Updated

Architecture Version 1.0