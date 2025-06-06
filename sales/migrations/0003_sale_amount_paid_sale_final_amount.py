# Generated by Django 5.2 on 2025-05-13 17:43

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0002_remove_sale_amount_paid_uzs_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='sale',
            name='amount_paid',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=17, verbose_name="To'langan Summa (UZS)"),
        ),
        migrations.AddField(
            model_name='sale',
            name='final_amount',
            field=models.DecimalField(decimal_places=2, default=1, max_digits=17, verbose_name='Yakuniy Narx (sotuvchi tushib berilgan narx)'),
            preserve_default=False,
        ),
    ]
