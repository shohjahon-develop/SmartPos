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
        max_length=5, # EAN-14 uchun prefiks uzunligini moslang (masalan, 2-5 raqam)
        unique=True,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^[0-9]*$', 'Faqat raqamlar ruxsat etilgan.')], # Faqat raqamlar
        verbose_name="Shtrix-kod Prefiksi (EAN-14 uchun raqamlar)",
        help_text="Ushbu kategoriyadagi mahsulotlar shtrix-kodi uchun boshlang'ich raqam(lar)."
    )

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
    price_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                    verbose_name="Sotish Narxi (USD)")
    price_uzs = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True,
                                    verbose_name="Sotish Narxi (UZS)") # Avtomatik hisoblanadi


    purchase_price_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                             verbose_name="Olingan Narxi (USD)")
    purchase_price_uzs = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True,
                                             verbose_name="Olingan Narxi (UZS)")
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

    # def calculate_price_uzs(self, rate=None):
    #     """UZS narxini joriy kurs bo'yicha hisoblaydi (Decimal bilan)"""
    #     if rate is None:
    #         try:
    #             rate_instance = CurrencyRate.load()
    #             # Kursni aniq Decimal ga o'tkazamiz
    #             rate = Decimal(rate_instance.usd_to_uzs_rate)
    #         except CurrencyRate.DoesNotExist:
    #             # 0 ni ham Decimal sifatida belgilaymiz
    #             rate = Decimal(0)
    #         except Exception as e:  # Boshqa xatoliklarni ham ushlash
    #             print(f"Error loading currency rate: {e}")
    #             rate = Decimal(0)  # Xatolik bo'lsa kursni 0 deb olamiz
    #     else:
    #         # Agar rate argument sifatida kelgan bo'lsa ham Decimal ga o'tkazamiz
    #         try:
    #             rate = Decimal(rate)
    #         except Exception as e:
    #             print(f"Invalid rate passed to calculate_price_uzs: {rate}. Error: {e}")
    #             rate = Decimal(0)
    #
    #     # Sotish narxini hisoblash
    #     if self.price_usd is not None:
    #         # Endi ikkalasi ham Decimal (yoki biri Decimal(0))
    #         self.price_uzs = self.price_usd * rate
    #     else:
    #         self.price_uzs = Decimal(0)  # Yoki None? None mantiqliroq bo'lishi mumkin
    #
    #     # Olingan narxni hisoblash
    #     if self.purchase_price_usd is not None:
    #         self.purchase_price_uzs = self.purchase_price_usd * rate
    #     else:
    #         self.purchase_price_uzs = None  # None yaxshiroq
    #
    #     # Funksiya UZS narxini qaytarishi shart emas, self.price_uzs ga yozsa kifoya
    #     # return self.price_uzs

    def save(self, *args, **kwargs):
        # Narx validatsiyasi (kamida bitta sotish narxi va bitta olingan narx bo'lishi kerak)
        # Buni serializerda qilish qulayroq
        # Shtrix-kod unikalligini tekshirish
        if self.barcode:
            qs = Product.objects.filter(barcode=self.barcode)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({'barcode': ['Bu shtrix-kod allaqachon mavjud.']})
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = "Mahsulot"
        verbose_name_plural = "Mahsulotlar"
        # Bir do'konda shtrix-kod unikal bo'lishi kerak (agar None emas bo'lsa)
        # unique=True ni olib tashladik, endi unique_together ishlatamiz
        ordering = ['name']