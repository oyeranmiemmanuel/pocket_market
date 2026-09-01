# Generated manually for Phase 7 - commission calculations.
#
# Snapshots which affiliate (if any) is credited with referring this
# order, captured once at checkout time from the attribution cookie (see
# apps.affiliates.services.get_attributed_affiliate). Both fields are
# nullable/blank so this is safe against existing orders, which simply
# get affiliate=NULL, affiliate_code='' (no affiliate involved).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_orderitem_seller_orderitem_platform_commission_rate_and_more'),
        ('affiliates', '0002_affiliatelink_affiliateclick'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='affiliate',
            field=models.ForeignKey(
                blank=True,
                help_text='Affiliate credited with referring this order, if any.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='attributed_orders',
                to='affiliates.affiliateprofile',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='affiliate_code',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]