# Marketplace Frontend Roadmap, section 6 - "Seller Product Creation &
# Commission UI". The seller-facing form now lets a seller set their own
# affiliate_commission_rate (previously form-only, admin/platform set),
# so the field needs its own hard floor/ceiling at the model layer -
# HTML min/max + JS clamp on the form is UX only and can be bypassed by
# posting directly to the view, so this AlterField is the real backend
# guard the roadmap calls for ("backend validation remains mandatory").

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models

from apps.core.constants import (
    AFFILIATE_COMMISSION_RATE_MAX,
    AFFILIATE_COMMISSION_RATE_MIN,
)


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0005_merge_20260905_1031'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='affiliate_commission_rate',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=5,
                null=True,
                validators=[
                    MinValueValidator(AFFILIATE_COMMISSION_RATE_MIN),
                    MaxValueValidator(AFFILIATE_COMMISSION_RATE_MAX),
                ],
                help_text=(
                    f"Affiliate commission percentage for this specific "
                    f"product, from {AFFILIATE_COMMISSION_RATE_MIN}% to "
                    f"{AFFILIATE_COMMISSION_RATE_MAX}%. Leave blank to "
                    f"fall through to the seller's rate, then the "
                    f"platform default."
                ),
            ),
        ),
    ]
