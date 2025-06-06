# Generated by Django 5.2 on 2025-05-20 08:44

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0003_sale_amount_paid_sale_final_amount'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sale',
            name='amount_paid',
        ),
        migrations.RemoveField(
            model_name='sale',
            name='amount_paid_currency',
        ),
        migrations.RemoveField(
            model_name='sale',
            name='final_amount',
        ),
        migrations.RemoveField(
            model_name='sale',
            name='total_amount_currency',
        ),
        migrations.AddField(
            model_name='sale',
            name='amount_actually_paid_at_sale',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=17, verbose_name="Sotuv Paytida Haqiqatda To'langan (sotuv valyutasida)"),
        ),
        migrations.AddField(
            model_name='sale',
            name='final_amount_currency',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=17, verbose_name='Yakuniy Summa (sotuv valyutasida, chegirma bilan)'),
        ),
        migrations.AddField(
            model_name='sale',
            name='original_total_amount_currency',
            field=models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=17, verbose_name='Asl Jami Summa (sotuv valyutasida, chegirmasiz)'),
        ),
    ]
