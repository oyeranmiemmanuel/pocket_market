# Checkout

Handled by `apps.orders.views.checkout_view` (`/orders/checkout/`, login
required).

## Flow

1. Reads the current user's cart (`apps.cart.services.get_or_create_cart`).
2. Empty cart -> redirect to `/cart/` with a message.
3. Validates stock for every cart line (`apps.orders.services.checkout.validate_cart_stock`)
   *before* rendering the form, and again on submit (stock can change
   between viewing and submitting).
4. `CheckoutForm` (`apps.orders.forms`) collects contact info + shipping
   address in one step.
5. On valid submit, `apps.orders.services.create_order_from_cart` snapshots
   the cart into a real `Order` + `OrderItem`s + `ShippingAddress`
   (see 14_ORDERS.md).
6. Redirects to `payments:initiate` for that order (see 15_PAYMENTS.md).

## What checkout deliberately does NOT do

- Does not touch `Product.stock` - that only happens once payment
  succeeds (16_INVENTORY.md), so an abandoned/unpaid order never holds
  stock hostage.
- Does not clear the cart - same reason, only happens on payment success.

## Template

`templates/orders/checkout.html` - form + live order summary side by side.
