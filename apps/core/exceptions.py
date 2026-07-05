"""
Base exceptions for the service layer.

Per ARCHITECTURE.MD, business logic lives in `services/` modules inside
each app, not in views. Services should raise these (or app-specific
subclasses of them) instead of generic Exception/ValueError, so views can
catch them predictably and turn them into proper HTTP responses.

Example (inside catalog/services/products.py):

    from app.core.exceptions import NotFoundError

    class ProductNotFound(NotFoundError):
        pass

    def get_product(product_id):
        try:
            return Product.active.get(pk=product_id)
        except Product.DoesNotExist:
            raise ProductNotFound(f"Product {product_id} not found")
"""


class ApplicationError(Exception):
    """Base class for all deliberate, expected application errors."""


class NotFoundError(ApplicationError):
    """Raised when a requested resource does not exist."""


class ValidationFailedError(ApplicationError):
    """Raised when input fails a business rule (not a form/field error)."""


class PermissionDeniedError(ApplicationError):
    """Raised when the current user isn't allowed to perform an action."""


class ConflictError(ApplicationError):
    """Raised when an action can't complete due to current object state
    (e.g. trying to pay for an already-paid order)."""