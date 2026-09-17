# Marketplace Frontend Roadmap, section 6 - "add product catigories
# (shoe, shirt, trouser, snikers, watch, phone, tv, electronic, cream,
# boby care, laptop and lot more)".
#
# get_or_create so this is safe to re-run and won't clobber a category a
# seller/admin already renamed or re-described by hand. Reversible: the
# reverse migration only removes rows that still have their seeded
# description untouched, and only if no product has been assigned to
# them - it never deletes a category that's actually in use.

from django.db import migrations
from django.utils.text import slugify

SEED_CATEGORIES = [
    ("Shoes", "Everyday, formal, and casual footwear."),
    ("Sneakers", "Athletic and lifestyle sneakers/trainers."),
    ("Shirts", "T-shirts, polos, and button-up shirts."),
    ("Trousers", "Trousers, jeans, and other pants."),
    ("Watches", "Wristwatches and smartwatches."),
    ("Phones", "Smartphones and feature phones."),
    ("Laptops", "Laptops and notebook computers."),
    ("TVs", "Televisions and TV accessories."),
    ("Electronics", "General consumer electronics and gadgets."),
    ("Cream", "Skincare and cosmetic creams."),
    ("Body Care", "Body care, hygiene, and personal care products."),
    ("Bags", "Handbags, backpacks, and luggage."),
    ("Jewelry", "Rings, necklaces, bracelets, and other jewelry."),
    ("Home Appliances", "Kitchen and household appliances."),
    ("Accessories", "Belts, sunglasses, hats, and other accessories."),
    ("Furniture", "Home and office furniture."),
    ("Beauty", "Makeup, fragrances, and beauty products."),
    ("Sportswear", "Athletic clothing and sports gear."),
    ("Groceries", "Food, drinks, and household groceries."),
    ("Books", "Books, magazines, and stationery."),
]


def seed_categories(apps, schema_editor):
    # Historical models from apps.get_model() don't carry
    # Category.save()'s auto-slug override, so the slug has to be set
    # by hand here or every row after the first would collide on the
    # unique-but-blank slug field.
    Category = apps.get_model("catalog", "Category")
    for name, description in SEED_CATEGORIES:
        Category.objects.get_or_create(
            name=name,
            defaults={"description": description, "slug": slugify(name)},
        )


def unseed_categories(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    seeded_names = [name for name, _ in SEED_CATEGORIES]
    for category in Category.objects.filter(name__in=seeded_names):
        expected_description = dict(SEED_CATEGORIES)[category.name]
        # Only remove it if it's untouched and unused - never delete a
        # category a seller has actually assigned products to, or one an
        # admin has since edited by hand.
        # Historical models don't carry BaseModel's soft-delete override,
        # so this .delete() is already a real row removal - which is
        # what reversing a seed should do.
        if (
            category.description == expected_description
            and not category.products.exists()
        ):
            category.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0006_alter_product_affiliate_commission_rate'),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
