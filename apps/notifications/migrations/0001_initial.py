import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('category', models.CharField(choices=[
                    ('order_placed', 'Order Placed'),
                    ('payment_successful', 'Payment Successful'),
                    ('order_processing', 'Order Processing'),
                    ('order_shipped', 'Order Shipped'),
                    ('order_delivered', 'Order Delivered'),
                    ('seller_application_approved', 'Seller Application Approved'),
                    ('seller_application_rejected', 'Seller Application Rejected'),
                    ('seller_new_order', 'New Order'),
                    ('seller_payout_status', 'Payout Status'),
                    ('affiliate_new_conversion', 'New Conversion'),
                    ('affiliate_commission_confirmed', 'Commission Confirmed'),
                    ('affiliate_commission_cancelled', 'Commission Cancelled'),
                    ('affiliate_payout_status', 'Payout Status'),
                ], max_length=40)),
                ('message', models.CharField(max_length=255)),
                ('url', models.CharField(blank=True, max_length=255)),
                ('is_read', models.BooleanField(default=False)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['user', 'is_read', 'created_at'], name='notifications_user_read_idx'),
        ),
    ]
