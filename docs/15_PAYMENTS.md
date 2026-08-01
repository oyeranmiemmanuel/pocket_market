# Payments

`apps.payments` - Paystack integration, same API call pattern as the
legacy `apps/views.py` buy_now/checkout flow, generalized to work against
a multi-item `orders.Order` instead of a single `Product`.

## Model

**`Payment`** - one row per payment *attempt* (not unique on order, so a
failed attempt can be retried with a fresh reference without losing
history). `reference` (unique, `PAY-...`), `provider` (`paystack`),
`status` (`pending`/`success`/`failed`), `amount`, `provider_reference`
(Paystack's own transaction reference), `paid_at`.

## Flow

1. `initiate_payment` view (`/payments/initiate/<order_reference>/`,
   login + ownership required) creates a `Payment` row and calls
   Paystack's `/transaction/initialize`, then redirects the browser to
   the returned `authorization_url`.
2. User pays on Paystack's hosted page.
3. **Two independent paths both confirm the same payment** (standard
   practice - the browser redirect can be interrupted, the webhook can't):
   - `payment_callback` (`/payments/callback/`) - Paystack redirects the
     user's browser back here with `?reference=...` after payment.
   - `paystack_webhook` (`/payments/webhook/`) - Paystack calls this
     server-to-server. Signature verified via HMAC-SHA512 against
     `PAYSTACK_SECRET_KEY`, same pattern as the legacy webhook.
4. Both paths call the same `verify_payment(reference)` service function,
   which is **idempotent** - calling it twice for an already-successful
   payment is a safe no-op (checked and tested: stock is not
   double-decremented if both the callback and webhook fire for the same
   payment).
5. On confirmed success: `Payment.status = success`, `Order.status = paid`,
   stock decremented per `OrderItem` (16_INVENTORY.md), cart cleared.
6. On failure: both `Payment` and `Order` marked `failed`.

## Templates

`templates/payments/success.html`, `templates/payments/failed.html` -
these existed before as bare placeholders; rewritten to show real order
data. Also fixed a pre-existing bug found while working on this: the
*legacy* monolith checkout (`apps/views.py`) was rendering from
`payment/...` (singular, nonexistent folder) instead of `payments/...`
(plural, the real folder) - every legacy checkout hit was a hard crash
until this was fixed.
