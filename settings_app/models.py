# settings_app/models.py
from django.db import models
from django.core.cache import cache
from django.utils import timezone

class SingletonModel(models.Model):
    """Faqat bitta yozuvga ega bo'lish uchun abstract model"""
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super(SingletonModel, self).save(*args, **kwargs)
        cache.delete(self.__class__.__name__) # Keshni tozalash

    def delete(self, *args, **kwargs):
        pass # O'chirishni bloklash

    @classmethod
    def load(cls):
        """Yagona instansiyani keshdan yoki DB dan olish"""
        instance = cache.get(cls.__name__)
        if not instance:
            instance, created = cls.objects.get_or_create(pk=1)
            # Yaratilganda default qiymatlarni o'rnatish (agar kerak bo'lsa)
            # if created:
            #     instance.save() # Default qiymatlarni saqlash uchun
            cache.set(cls.__name__, instance, timeout=None) # Keshda saqlash (cheksiz)
        return instance

class StoreSettings(SingletonModel):
    name = models.CharField(max_length=255, default="Smart POS Do'koni", verbose_name="Do'kon nomi")
    address = models.TextField(blank=True, null=True, verbose_name="Manzil")
    phone = models.CharField(max_length=100, blank=True, null=True, verbose_name="Telefon raqami")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")

    class Meta:
        verbose_name = "Do'kon Sozlamasi"
        verbose_name_plural = "Do'kon Sozlamalari"

    def __str__(self):
        return self.name

class CurrencyRate(SingletonModel):
    usd_to_uzs_rate = models.DecimalField(max_digits=15, decimal_places=2, default=13000.00, verbose_name="USD->UZS Kursi")
    last_updated = models.DateTimeField(default=timezone.now, verbose_name="So'nggi yangilanish")

    def save(self, *args, **kwargs):
        self.last_updated = timezone.now()
        super().save(*args, **kwargs)
        # Bu yerda kurs o'zgarganda qilinadigan qo'shimcha amallar bo'lishi mumkin
        # Masalan, barcha mahsulotlarning UZS narxini yangilash (agar shunday talab bo'lsa)

    class Meta:
        verbose_name = "Valyuta Kursi"
        verbose_name_plural = "Valyuta Kurslari"

    def __str__(self):
        return f"1 USD = {self.usd_to_uzs_rate} UZS ({self.last_updated.strftime('%Y-%m-%d %H:%M')})"