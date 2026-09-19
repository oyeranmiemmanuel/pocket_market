from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0006_refund_approved_at_refund_item_received_at_and_more"),
        ("orders", "0007_orderitem_delivered_at"),
    ]

    operations = []
