# Generated manually for Phase 7 - commission calculations.
#
# Creates AffiliateCommission - the conversion + commission record from
# spec sections 14/15. One row per (order_item, affiliate), created once
# at payment-success time. Refunds later create a *second* row
# (reversal_of pointing back at the original) rather than mutating or
# deleting it - see the model's docstring.

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('affiliates', '0002_affiliatelink_affiliateclick'),
        ('orders', '0004_order_affiliate_order_affiliate_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='AffiliateCommission',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('order_amount', models.DecimalField(decimal_places=2, help_text='Gross line-item amount (OrderItem.subtotal) this commission was calculated from.', max_digits=12)),
                ('commission_rate', models.DecimalField(decimal_places=2, max_digits=5)),
                ('commission_amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('confirmed', 'Confirmed'), ('available', 'Available'), ('paid', 'Paid'), ('cancelled', 'Cancelled'), ('reversed', 'Reversed')], default='pending', max_length=20)),
                ('notes', models.CharField(blank=True, max_length=255)),
                ('affiliate', models.ForeignKey(help_text="PROTECT, not SET_NULL/CASCADE - a commission must never lose track of who it's owed to, even if we later add affiliate deletion.", on_delete=django.db.models.deletion.PROTECT, related_name='commissions', to='affiliates.affiliateprofile')),
                ('affiliate_link', models.ForeignKey(blank=True, help_text='The link this conversion is credited through, if the affiliate had generated one for this exact product. Null does not invalidate the commission - attribution is by affiliate code, not by a specific link.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='commissions', to='affiliates.affiliatelink')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='affiliate_commissions', to='orders.order')),
                ('order_item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='affiliate_commissions', to='orders.orderitem')),
                ('reversal_of', models.ForeignKey(blank=True, help_text='Set only on a reversal row - points back at the original commission it cancels out.', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reversals', to='affiliates.affiliatecommission')),
            ],
            options={
                'db_table': 'affiliate_commissions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='affiliatecommission',
            index=models.Index(fields=['affiliate', 'status'], name='affiliate_c_affilia_1f1f0a_idx'),
        ),
        migrations.AddIndex(
            model_name='affiliatecommission',
            index=models.Index(fields=['order', 'status'], name='affiliate_c_order_i_5c9d3e_idx'),
        ),
        migrations.AddConstraint(
            model_name='affiliatecommission',
            constraint=models.UniqueConstraint(condition=models.Q(('reversal_of__isnull', True)), fields=('order_item',), name='unique_original_commission_per_order_item'),
        ),
    ]