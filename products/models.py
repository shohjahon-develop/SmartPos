# products/models.py
from django.core.validators import RegexValidator
from django.db import models
from django.core.exceptions import ValidationError
from settings_app.models import CurrencyRate # Kursni olish uchun

from decimal import Decimal

class Kassa(models.Model):
    """Kassa, Filial yoki Ombor"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Nomi")
    location = models.CharField(max_length=255, blank=True, null=True, verbose_name="Joylashuvi")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv") # Aktiv/Nofaol

    class Meta:
        verbose_name = "Kassa/Filial"
        verbose_name_plural = "Kassalar/Filiallar"
        ordering = ['name']

    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nomi")
    description = models.TextField(blank=True, null=True, verbose_name="Tavsifi")
    barcode_prefix = models.CharField(
        max_length=10,
        unique=True,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^[0-9a-zA-Z]*$', 'Faqat harf va raqamlar ruxsat etilgan.')],
        verbose_name="Shtrix-kod Prefiksi",
        help_text="Bu kategoriya uchun shtrix-kod boshlanadigan belgi(lar). Masalan: 'IPH', '01', 'SAM'."
    )

    class Meta:
        verbose_name = "Kategoriya"
        verbose_name_plural = "Kategoriyalar"
        ordering = ['name']

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=255, verbose_name="Nomi")
    category = models.ForeignKey(Category, related_name='products', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Kategoriya")
    barcode = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        verbose_name="Shtrix-kod"
    )
    price_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Sotish Narxi (USD)")
    price_uzs = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Sotish Narxi (UZS)")
    purchase_price_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Olingan Narxi (USD)")
    purchase_price_uzs = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True, verbose_name="Olingan Narxi (UZS)")
    purchase_date = models.DateField(null=True, blank=True, verbose_name="Olingan Sana")
    description = models.TextField(blank=True, null=True, verbose_name="Tavsifi (ixtiyoriy)")
    storage_capacity = models.CharField(max_length=50, blank=True, null=True, verbose_name="Sig'imi (Masalan: 128GB)")
    color = models.CharField(max_length=50, blank=True, null=True, verbose_name="Rangi")
    series_region = models.CharField(max_length=100, blank=True, null=True, verbose_name="Seriyasi (Region, Masalan: LL/A)")
    battery_health = models.PositiveIntegerField(null=True, blank=True, verbose_name="Batareya Holati (%)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan sana")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")

    def save(self, *args, **kwargs):
        if self.barcode: # Faqat barcode mavjud bo'lsa tekshiramiz
            qs = Product.objects.filter(barcode=self.barcode)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({'barcode': ['Bu shtrix-kod allaqachon mavjud.']})
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Mahsulot"
        verbose_name_plural = "Mahsulotlar"
        ordering = ['name']