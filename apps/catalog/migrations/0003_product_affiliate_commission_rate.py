# Generated manually for Phase 7 - commission calculations.
#
# Adds the product-level rung of the affiliate commission hierarchy
# (spec section 16): Product.affiliate_commission_rate ->
# Seller.affiliate_commission_rate -> platform default. Nullable, so all
# existing products simply fall through to the next level - no backfill
# required.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_product_commission_rate_product_seller'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='affiliate_commission_rate',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=5,
                null=True,
                help_text="Affiliate commission percentage for this specific "
                           "product. Leave blank to fall through to the seller's "
                           "rate, then the platform default.",
            ),
        ),
    ]