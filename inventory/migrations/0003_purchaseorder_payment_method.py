# Generated by Django 5.2 on 2025-06-13 12:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0002_supplier_purchaseorder_purchaseorderitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaseorder',
            name='payment_method',
            field=models.CharField(choices=[('CASH', 'Naqd'), ('TRANSFER', "Bank O'tkazmasi"), ('CREDIT', 'Nasiya (Yetkazib beruvchidan)')], default='CREDIT', max_length=20, verbose_name="Xarid To'lov Usuli"),
        ),
    ]
