# products/models.py
from django.db import models
from django.core.exceptions import ValidationError
from settings_app.models import CurrencyRate # Kursni olish uchun



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
    """Mahsulot Kategoriyalari"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Nomi")
    description = models.TextField(blank=True, null=True, verbose_name="Tavsifi")

    class Meta:
        verbose_name = "Kategoriya"
        verbose_name_plural = "Kategoriyalar"
        ordering = ['name']

    def __str__(self):
        return self.name

class Product(models.Model):
    """Mahsulot"""
    name = models.CharField(max_length=255, verbose_name="Nomi")
    category = models.ForeignKey(Category, related_name='products', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Kategoriya")
    barcode = models.CharField(max_length=100, unique=True, blank=True, null=True, verbose_name="Shtrix-kod") # unique=True ni store bilan birga unique_together ga ko'chiramiz

    # --- Sotish Narxlari ---
    price_usd = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Sotish Narxi (USD)")
    price_uzs = models.DecimalField(max_digits=15, decimal_places=2, blank=True, verbose_name="Sotish Narxi (UZS)") # Avtomatik hisoblanadi

    # --- Olingan Narxlar (Frontend talabi) ---
    purchase_price_usd = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Olingan Narxi (USD)"
    )
    purchase_price_uzs = models.DecimalField(
        max_digits=15, decimal_places=2, blank=True, verbose_name="Olingan Narxi (UZS)" # Avtomatik hisoblanadi
    )
    purchase_date = models.DateField(null=True, blank=True, verbose_name="Olingan Sana")

    # --- Boshqa Xususiyatlar (Frontend talabi) ---
    description = models.TextField(blank=True, null=True, verbose_name="Tavsifi (ixtiyoriy)")
    storage_capacity = models.CharField(max_length=50, blank=True, null=True, verbose_name="Sig'imi (Masalan: 128GB)")
    color = models.CharField(max_length=50, blank=True, null=True, verbose_name="Rangi")
    series_region = models.CharField(max_length=100, blank=True, null=True, verbose_name="Seriyasi (Region, Masalan: LL/A)")
    battery_health = models.PositiveIntegerField(null=True, blank=True, verbose_name="Batareya Holati (%)") # Faqat telefonlar uchun

    # --- Tizim Maydonlari ---
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan sana")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv") # Sotuvda ko'rinishi uchun

    def calculate_price_uzs(self, rate=None):
        """UZS narxini joriy kurs bo'yicha hisoblaydi"""
        if rate is None:
            try:
                rate_instance = CurrencyRate.load()
                rate = rate_instance.usd_to_uzs_rate
            except CurrencyRate.DoesNotExist:
                rate = 0
        if self.price_usd is not None:
             self.price_uzs = self.price_usd * rate
        else:
             self.price_uzs = 0 # Yoki None?

        # Olingan narxni ham hisoblash
        if self.purchase_price_usd is not None:
             self.purchase_price_uzs = self.purchase_price_usd * rate
        else:
             self.purchase_price_uzs = None # Yoki 0? None yaxshiroq

        return self.price_uzs

    def save(self, *args, **kwargs):
        # Saqlashdan oldin UZS narxlarini hisoblash
        self.calculate_price_uzs()
        # Shtrix-kod unikalligini tekshirish (do'kon ichida)
        if self.barcode:
            qs = Product.objects.filter(barcode=self.barcode)  # store filtri olib tashlandi
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({'barcode': ['Bu shtrix-kod allaqachon mavjud.']})
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.store.name})"

    class Meta:
        verbose_name = "Mahsulot"
        verbose_name_plural = "Mahsulotlar"
        # Bir do'konda shtrix-kod unikal bo'lishi kerak (agar None emas bo'lsa)
        # unique=True ni olib tashladik, endi unique_together ishlatamiz
        ordering = ['name']