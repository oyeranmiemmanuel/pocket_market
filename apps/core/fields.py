"""
Field-level encryption for sensitive KYC data (national ID numbers,
driver's licence numbers, and similar credentials) - per the KYC phase-1
spec: "Encryption/protection appropriate to the data ... No sensitive
values in URLs, affiliate links, analytics events, or logs."

Symmetric (Fernet) encryption is used, not one-way hashing, because
these values must be recoverable for verified use later (admin review,
future automated verification) - not just checked for equality.

Requires settings.KYC_FIELD_ENCRYPTION_KEY - see config/settings.py for
how to generate one.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


def _get_fernet():
    from cryptography.fernet import Fernet

    key = getattr(settings, "KYC_FIELD_ENCRYPTION_KEY", None)
    if not key:
        raise ImproperlyConfigured(
            "KYC_FIELD_ENCRYPTION_KEY is not set - required to store/read "
            "encrypted KYC fields. See config/settings.py."
        )
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


class _MaskableStr(str):
    """Marks a value as already-decrypted so to_python() doesn't decrypt it twice."""
    _kyc_decrypted = True


class EncryptedCharField(models.CharField):
    """
    Transparently encrypts on save, decrypts on load. `max_length` here
    is the plaintext limit used for form/validator purposes - the actual
    column is stored as TEXT (via get_internal_type) since ciphertext is
    longer than the plaintext.
    """

    description = "An encrypted CharField"

    def get_internal_type(self):
        return "TextField"

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def to_python(self, value):
        if value in (None, ""):
            return value
        if getattr(value, "_kyc_decrypted", False):
            return value
        try:
            decrypted = _get_fernet().decrypt(value.encode()).decode()
        except Exception:
            # Not valid ciphertext - most likely plaintext being assigned
            # in Python before its first save (e.g. a form's cleaned_data).
            return value
        return _MaskableStr(decrypted)

    def get_prep_value(self, value):
        if value in (None, ""):
            return value
        return _get_fernet().encrypt(str(value).encode()).decode()


def mask_value(value, visible=4):
    """
    Masks all but the last `visible` characters, e.g.
    mask_value("12345678901") -> "*******8901". Used for admin list
    displays so full values are never shown by default - opening the
    actual detail/change view is a deliberate, logged action
    (see apps.kyc.services.log_kyc_access).
    """
    if not value:
        return ""
    value = str(value)
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]