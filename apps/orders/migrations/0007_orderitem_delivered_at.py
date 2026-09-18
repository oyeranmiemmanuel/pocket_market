# Marketplace Frontend Roadmap section 21 - "Buyer Protection UI". Adds
# the one piece of information genuinely missing anywhere in the
# codebase for that feature: an actual timestamp for "when did this
# item first become Delivered" - the clock the 48-hour buyer protection
# countdown runs from (apps.core.constants.BUYER_PROTECTION_WINDOW_HOURS).
#
# This is NOT a duplicate of anything apps.sellers.order_status already
# derives (that module computes a richer *status*, e.g. distinguishing
# Delivered from Completed, from several other apps' existing fields -
# see its own docstring) - none of those existing fields are a
# timestamp, so there's nothing already in the system this could drift
# out of sync with.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0006_savedaddress_and_orderseller_delivery"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="delivered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
