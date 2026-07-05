"""
Generate short, human-friendly unique reference codes.

Used for things like order references, delivery tracking codes, and
payment references — anywhere a model needs a public-facing ID that
isn't the raw database primary key.
"""

import random
import string
import uuid


def generate_reference(prefix: str = "", length: int = 10) -> str:
    """
    Build a reference like "ORD-7F3K9QZP1A".

    `length` controls how many random base32-style characters follow the
    prefix. Uses uuid4 for entropy, then trims/pads with random choices
    to hit the requested length exactly.
    """
    raw = uuid.uuid4().hex.upper()
    alphabet = string.ascii_uppercase + string.digits
    code = raw[:length] if len(raw) >= length else raw + "".join(
        random.choices(alphabet, k=length - len(raw))
    )
    return f"{prefix}-{code}" if prefix else code