import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sellers', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Payout',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('status', models.CharField(choices=[('requested', 'Requested'), ('paid', 'Paid'), ('failed', 'Failed')], default='requested', max_length=20)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('failure_reason', models.TextField(blank=True)),
                ('seller', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payouts', to='sellers.sellerprofile')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
