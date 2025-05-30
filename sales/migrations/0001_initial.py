# Generated by Django 5.2 on 2025-05-09 05:42

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('installments', '0001_initial'),
        ('products', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=255, verbose_name="To'liq ismi")),
                ('phone_number', models.CharField(max_length=20, unique=True, verbose_name='Telefon raqami')),
                ('email', models.EmailField(blank=True, max_length=254, null=True, verbose_name='Email (ixtiyoriy)')),
                ('address', models.TextField(blank=True, null=True, verbose_name='Manzil (ixtiyoriy)')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name="Qo'shilgan sana")),
            ],
            options={
                'verbose_name': 'Mijoz',
                'verbose_name_plural': 'Mijozlar',
                'ordering': ['full_name'],
            },
        ),
        migrations.CreateModel(
            name='Sale',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_amount_usd', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Umumiy summa (USD)')),
                ('total_amount_uzs', models.DecimalField(decimal_places=2, default=0, max_digits=17, verbose_name='Umumiy summa (UZS)')),
                ('payment_type', models.CharField(choices=[('Naqd', 'Naqd'), ('Karta', 'Karta'), ('Nasiya', 'Nasiya'), ('Aralash', 'Aralash')], max_length=10, verbose_name="To'lov turi")),
                ('amount_paid_uzs', models.DecimalField(decimal_places=2, default=0, help_text="Aralash yoki Nasiya to'lovining boshlang'ich qismi", max_digits=17, verbose_name="To'langan summa (UZS)")),
                ('status', models.CharField(choices=[('Completed', 'Yakunlangan'), ('Returned', 'Qaytarilgan'), ('Partially Returned', 'Qisman Qaytarilgan'), ('Pending', 'Kutilmoqda'), ('Cancelled', 'Bekor qilingan')], default='Completed', max_length=20, verbose_name='Holati')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Sana va vaqt')),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='purchases', to='sales.customer', verbose_name='Mijoz')),
                ('kassa', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sales_registered', to='products.kassa', verbose_name='Kassa/Filial')),
                ('seller', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sales_conducted', to=settings.AUTH_USER_MODEL, verbose_name='Sotuvchi')),
            ],
            options={
                'verbose_name': 'Sotuv',
                'verbose_name_plural': 'Sotuvlar',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SaleItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)], verbose_name='Miqdori')),
                ('price_at_sale_usd', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Narx (USD) (sotuv paytida)')),
                ('price_at_sale_uzs', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='Narx (UZS) (sotuv paytida)')),
                ('quantity_returned', models.PositiveIntegerField(default=0, verbose_name='Qaytarilgan miqdor')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sale_items', to='products.product', verbose_name='Mahsulot')),
                ('sale', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='sales.sale', verbose_name='Sotuv')),
            ],
            options={
                'verbose_name': 'Sotuv Elementi',
                'verbose_name_plural': 'Sotuv Elementlari',
                'unique_together': {('sale', 'product')},
            },
        ),
        migrations.CreateModel(
            name='SaleReturn',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField(blank=True, null=True, verbose_name='Qaytarish sababi')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Qaytarilgan sana')),
                ('total_returned_amount_uzs', models.DecimalField(decimal_places=2, default=0, max_digits=17, verbose_name='Jami qaytarilgan summa (UZS)')),
                ('original_sale', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='returns', to='sales.sale', verbose_name='Asl Sotuv')),
                ('returned_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Qaytaruvchi Xodim')),
            ],
            options={
                'verbose_name': 'Sotuv Qaytarish',
                'verbose_name_plural': 'Sotuv Qaytarishlar',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='KassaTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=17, verbose_name='Summa (UZS)')),
                ('transaction_type', models.CharField(choices=[('SALE', 'Sotuvdan Kirim'), ('INSTALLMENT', 'Nasiyadan Kirim'), ('CASH_IN', 'Kirim (Boshqa)'), ('CASH_OUT', 'Chiqim (Xarajat)'), ('REFUND', 'Qaytarish (Chiqim)')], max_length=20, verbose_name='Amaliyot Turi')),
                ('comment', models.TextField(blank=True, null=True, verbose_name='Izoh')),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Sana va Vaqt')),
                ('kassa', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transactions', to='products.kassa', verbose_name='Kassa')),
                ('related_installment_payment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kassa_transactions', to='installments.installmentpayment')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Xodim')),
                ('related_sale', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kassa_transactions', to='sales.sale')),
                ('related_return', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kassa_transactions', to='sales.salereturn')),
            ],
            options={
                'verbose_name': 'Kassa Amaliyoti',
                'verbose_name_plural': 'Kassa Amaliyotlari',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='SaleReturnItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity_returned', models.PositiveIntegerField(verbose_name='Qaytarilgan miqdor (shu operatsiyada)')),
                ('sale_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='sales.saleitem', verbose_name='Asl Sotuv Elementi')),
                ('sale_return', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='sales.salereturn', verbose_name='Qaytarish Operatsiyasi')),
            ],
            options={
                'verbose_name': 'Qaytarilgan Element',
                'verbose_name_plural': 'Qaytarilgan Elementlar',
            },
        ),
    ]
