# Generated manually for Phase 7 - commission calculations.
#
# Adds the seller-level rung of the affiliate commission hierarchy (spec
# section 16). Nullable, so every existing seller simply falls through to
# the platform default - no backfill required.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sellers', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='sellerprofile',
            name='affiliate_commission_rate',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=5,
                null=True,
                help_text="Affiliate commission percentage applied to this "
                           "seller's products by default (unless a product "
                           "overrides it). Leave blank to use the platform default.",
            ),
        ),
    ]