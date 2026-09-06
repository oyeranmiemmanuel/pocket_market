import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0004_order_affiliate_order_affiliate_code"),
    ]

    operations = [
        migrations.CreateModel(
            name="Refund",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("reason", models.TextField()),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("requested", "Requested"),
                            ("rejected", "Rejected"),
                            ("processing", "Processing"),
                            ("processed", "Processed"),
                            ("failed", "Failed"),
                        ],
                        default="requested",
                        max_length=20,
                    ),
                ),
                ("admin_notes", models.CharField(blank=True, max_length=255)),
                ("provider_reference", models.CharField(blank=True, max_length=100)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "order_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="refunds",
                        to="orders.orderitem",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="refund_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="refund_reviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "refunds",
                "ordering": ["-created_at"],
            },
        ),
    ]
