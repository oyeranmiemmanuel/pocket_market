"""
Unique slug generation helper for models with a `slug` field.
"""

from django.utils.text import slugify


def unique_slugify(instance, value: str, slug_field: str = "slug") -> str:
    """
    Return a slug for `value` that is unique for instance's model/table,
    appending -2, -3, ... if needed.

    Usage in a model's save():
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
    """
    model = instance.__class__
    base_slug = slugify(value)
    slug = base_slug
    counter = 2

    queryset = model.objects.exclude(pk=instance.pk) if instance.pk else model.objects.all()

    while queryset.filter(**{slug_field: slug}).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug