# Generated by Django 5.2 on 2025-05-10 11:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installments', '0002_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='installmentplan',
            name='total_amount_due',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=17, null=True, verbose_name="Jami To'lanishi Kerak (Foiz Bilan, UZS)"),
        ),
    ]
