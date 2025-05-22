# products/models.py
from django.core.validators import RegexValidator
from django.db import models
from django.core.exceptions import ValidationError
# from settings_app.models import CurrencyRate # Hozircha kerak emas
from decimal import Decimal
# from django.conf import settings # User uchun kerak emas bu modelda
from django.db.models.signals import post_save # Signal uchun
from django.dispatch import receiver # Signal uchun

class Kassa(models.Model):
    """Kassa, Filial yoki Ombor"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Nomi")
    location = models.CharField(max_length=255, blank=True, null=True, verbose_name="Joylashuvi")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")

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
        max_length=10, unique=True, blank=True, null=True,
        validators=[RegexValidator(r'^[0-9a-zA-Z]*$', 'Faqat harf va raqamlar ruxsat etilgan.')],
        verbose_name="Shtrix-kod Prefiksi",
        help_text="Bu kategoriya uchun shtrix-kod boshlanadigan belgi(lar). Masalan: 'IPH', '01'."
    )

    class Meta:
        verbose_name = "Kategoriya"
        verbose_name_plural = "Kategoriyalar"
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255, verbose_name="Nomi")
    category = models.ForeignKey(Category, related_name='products', on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name="Kategoriya")
    barcode = models.CharField(
        max_length=100, unique=True, blank=True, null=True,
        verbose_name="Shtrix-kod / IMEI"
    )
    price_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                    verbose_name="Sotish Narxi (USD)")
    price_uzs = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True,
                                    verbose_name="Sotish Narxi (UZS)")
    purchase_price_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                             verbose_name="Olingan Narxi (USD)")
    purchase_price_uzs = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True,
                                             verbose_name="Olingan Narxi (UZS)")
    purchase_date = models.DateField(null=True, blank=True, verbose_name="Olingan Sana")
    description = models.TextField(blank=True, null=True, verbose_name="Tavsifi (ixtiyoriy)")
    storage_capacity = models.CharField(max_length=50, blank=True, null=True, verbose_name="Sig'imi (Masalan: 128GB)")
    color = models.CharField(max_length=50, blank=True, null=True, verbose_name="Rangi")
    series_region = models.CharField(max_length=100, blank=True, null=True,
                                     verbose_name="Seriyasi (Region, Masalan: LL/A)")
    battery_health = models.PositiveIntegerField(null=True, blank=True,
                                                 verbose_name="Batareya Holati (%)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan sana")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")

    # YANGI QO'SHILDI: Yangi mahsulot qaysi kassaga birlamchi kirim qilinishi
    default_kassa_for_new_stock = models.ForeignKey(
        Kassa,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='default_new_products_stock', # related_name o'zgartirildi (unique bo'lishi uchun)
        verbose_name="Yangi mahsulot uchun standart kassa (omborga qo'shish uchun)"
    )

    def save(self, *args, **kwargs):
        if self.barcode:
            qs = Product.objects.filter(barcode=self.barcode)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({'barcode': ['Bu shtrix-kod yoki IMEI allaqachon mavjud.']})
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Mahsulot"
        verbose_name_plural = "Mahsulotlar"
        ordering = ['name']


# YANGI QO'SHILDI: Signal handler
@receiver(post_save, sender=Product)
def create_product_stock_on_product_creation(sender, instance, created, **kwargs):
    """
    Yangi Product yaratilganda, ProductStock ga yozuv qo'shadi.
    """
    if created: # Faqat yangi mahsulot yaratilganda ishlaydi
        from inventory.models import ProductStock # Circular importni oldini olish uchun shu yerda import

        target_kassa = instance.default_kassa_for_new_stock

        if not target_kassa:
            first_active_kassa = Kassa.objects.filter(is_active=True).order_by('id').first() # Barqaror natija uchun order_by('id')
            if first_active_kassa:
                target_kassa = first_active_kassa
            else:
                print(f"WARNING: Product '{instance.name}' uchun ProductStock yaratilmadi, chunki aktiv kassa topilmadi va mahsulotda standart kassa belgilanmagan.")
                return # Aktiv kassa topilmasa, hech narsa qilmaymiz

        if target_kassa:
            # ProductStock yozuvi mavjudligini tekshirib, yo'q bo'lsa yaratamiz
            stock, stock_created = ProductStock.objects.get_or_create(
                product=instance,
                kassa=target_kassa,
                defaults={'quantity': 0} # Boshlang'ich miqdor 0
            )
            if stock_created:
                print(f"SUCCESS: ProductStock for '{instance.name}' at Kassa '{target_kassa.name}' created with quantity 0.")
                # Bu yerda InventoryOperation yaratish shart emas, chunki bu faqat boshlang'ich qoldiq yozuvi.
                # Haqiqiy kirim alohida "Omborga Qo'shish" operatsiyasi bilan amalga oshiriladi.
            # else:
                # print(f"INFO: ProductStock for '{instance.name}' at Kassa '{target_kassa.name}' already existed (quantity: {stock.quantity}). No new stock record created by signal.")



# # products/models.py
# from django.core.validators import RegexValidator
# from django.db import models
# from django.core.exceptions import ValidationError
# from settings_app.models import CurrencyRate # Kursni olish uchun
#
# from decimal import Decimal
#
# class Kassa(models.Model):
#     """Kassa, Filial yoki Ombor"""
#     name = models.CharField(max_length=100, unique=True, verbose_name="Nomi")
#     location = models.CharField(max_length=255, blank=True, null=True, verbose_name="Joylashuvi")
#     is_active = models.BooleanField(default=True, verbose_name="Aktiv") # Aktiv/Nofaol
#
#     class Meta:
#         verbose_name = "Kassa/Filial"
#         verbose_name_plural = "Kassalar/Filiallar"
#         ordering = ['name']
#
#     def __str__(self):
#         return self.name
#
#
# # products/models.py
# from django.db import models
# from django.core.validators import RegexValidator
# from django.core.exceptions import ValidationError
#
#
# class Category(models.Model):
#     name = models.CharField(max_length=100, unique=True, verbose_name="Nomi")
#     description = models.TextField(blank=True, null=True, verbose_name="Tavsifi")
#     barcode_prefix = models.CharField(
#         max_length=10, unique=True, blank=True, null=True,
#         validators=[RegexValidator(r'^[0-9a-zA-Z]*$', 'Faqat harf va raqamlar ruxsat etilgan.')],
#         verbose_name="Shtrix-kod Prefiksi",
#         help_text="Bu kategoriya uchun shtrix-kod boshlanadigan belgi(lar). Masalan: 'IPH', '01'."
#     )
#
#     class Meta:
#         verbose_name = "Kategoriya"
#         verbose_name_plural = "Kategoriyalar"
#         ordering = ['name']
#
#     def __str__(self):
#         return self.name
#
#
# class Product(models.Model):
#     name = models.CharField(max_length=255, verbose_name="Nomi")
#     category = models.ForeignKey(Category, related_name='products', on_delete=models.SET_NULL, null=True, blank=True,
#                                  verbose_name="Kategoriya")
#
#     # Barcode endi IMEI ni ham o'z ichiga olishi mumkin
#     barcode = models.CharField(
#         max_length=100,
#         unique=True,  # Unikal bo'lishi kerak (ham barcode, ham IMEI uchun)
#         blank=True,  # Agar avtomatik generatsiya bo'lsa yoki IMEI kiritilmasa (lekin serializer talab qiladi)
#         null=True,
#         verbose_name="Shtrix-kod / IMEI"
#     )
#     # imei maydoni olib tashlandi
#
#     # ... (qolgan barcha maydonlar: price_usd, price_uzs, description, va hokazo - o'zgarishsiz) ...
#     price_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
#                                     verbose_name="Sotish Narxi (USD)")
#     price_uzs = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True,
#                                     verbose_name="Sotish Narxi (UZS)")
#     purchase_price_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
#                                              verbose_name="Olingan Narxi (USD)")
#     purchase_price_uzs = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True,
#                                              verbose_name="Olingan Narxi (UZS)")
#     purchase_date = models.DateField(null=True, blank=True, verbose_name="Olingan Sana")
#     description = models.TextField(blank=True, null=True, verbose_name="Tavsifi (ixtiyoriy)")
#     storage_capacity = models.CharField(max_length=50, blank=True, null=True, verbose_name="Sig'imi (Masalan: 128GB)")
#     color = models.CharField(max_length=50, blank=True, null=True, verbose_name="Rangi")
#     series_region = models.CharField(max_length=100, blank=True, null=True,
#                                      verbose_name="Seriyasi (Region, Masalan: LL/A)")  # iPhone uchun
#     battery_health = models.PositiveIntegerField(null=True, blank=True,
#                                                  verbose_name="Batareya Holati (%)")  # iPhone uchun
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")
#     updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan sana")
#     is_active = models.BooleanField(default=True, verbose_name="Aktiv")
#
#     def save(self, *args, **kwargs):
#         if self.barcode:  # Faqat barcode mavjud bo'lsa unikallikni tekshiramiz
#             qs = Product.objects.filter(barcode=self.barcode)
#             if self.pk:  # Agar obyekt yangilanayotgan bo'lsa
#                 qs = qs.exclude(pk=self.pk)
#             if qs.exists():
#                 raise ValidationError({'barcode': ['Bu shtrix-kod yoki IMEI allaqachon mavjud.']})
#         super().save(*args, **kwargs)
#
#     def __str__(self):
#         return self.name
#
#     class Meta:
#         verbose_name = "Mahsulot"
#         verbose_name_plural = "Mahsulotlar"
#         ordering = ['name']