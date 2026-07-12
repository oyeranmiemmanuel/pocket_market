"""
Reusable field validators shared across apps.
"""

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class PhoneNumberValidator:
    """Validates a local phone number has the expected number of digits."""

    message = "Phone number must be exactly 11 digits."
    code = "invalid_phone_number"

    def __call__(self, value):
        digits = str(value).strip()
        if not digits.isdigit() or len(digits) != 11:
            raise ValidationError(self.message, code=self.code)

    def __eq__(self, other):
        return isinstance(other, PhoneNumberValidator)


validate_phone_number = PhoneNumberValidator()
