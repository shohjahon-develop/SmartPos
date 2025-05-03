# inventory/models.py
from django.db import models
from django.conf import settings # User uchun
from products.models import Product, Kassa # Bog'liqlik uchun
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

class ProductStock(models.Model):
    """Har bir kassadagi mahsulot qoldig'i"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stocks', verbose_name="Mahsulot")
    kassa = models.ForeignKey(Kassa, on_delete=models.CASCADE, related_name='stocks', verbose_name="Kassa/Filial")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Miqdori (qoldiq)")
    minimum_stock_level = models.PositiveIntegerField(default=5, verbose_name="Minimal miqdor") # Default qiymatni moslang

    class Meta:
        unique_together = ('product', 'kassa') # Har bir mahsulot uchun kassada faqat bitta qoldiq yozuvi
        verbose_name = "Ombor Qoldig'i"
        verbose_name_plural = "Ombor Qoldiqlari"
        ordering = ['kassa', 'product__name']

    def __str__(self):
        return f"{self.product.name} @ {self.kassa.name}: {self.quantity}"

    @property
    def is_low_stock(self):
        """Mahsulot miqdori minimal darajadan pastligini tekshiradi"""
        return self.quantity < self.minimum_stock_level


class InventoryOperation(models.Model):
    """Ombor amaliyotlari tarixi"""
    class OperationType(models.TextChoices):
        ADD = 'ADD', 'Qo\'shish (Kirim)' # Yangi mahsulot yoki mavjudiga qo'shish
        REMOVE = 'REMOVE', 'Chiqarish (Hisobdan chiqarish)' # Sotuvdan tashqari (masalan, yaroqsiz)
        TRANSFER_OUT = 'TRANSFER_OUT', 'Ko\'chirish (Chiqish)'
        TRANSFER_IN = 'TRANSFER_IN', 'Ko\'chirish (Kirish)'
        SALE = 'SALE', 'Sotuv' # Sotuv ilovasidan yaratiladi
        RETURN = 'RETURN', 'Qaytarish' # Sotuv ilovasidan yaratiladi
        INITIAL = 'INITIAL', 'Boshlang\'ich qoldiq' # Boshlang'ich ma'lumot kiritish uchun

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='inventory_operations', verbose_name="Mahsulot")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='inventory_operations', verbose_name="Foydalanuvchi (Amaliyotchi)")
    kassa = models.ForeignKey(Kassa, on_delete=models.PROTECT, related_name='inventory_operations', verbose_name="Kassa/Filial")
    quantity = models.IntegerField(verbose_name="Miqdor (+/-)") # Qo'shish uchun musbat, chiqarish/sotuv uchun manfiy
    operation_type = models.CharField(max_length=20, choices=OperationType.choices, verbose_name="Amaliyot turi")
    comment = models.TextField(blank=True, null=True, verbose_name="Izoh")
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="Sana va vaqt")
    # Ko'chirish amaliyotlarini bog'lash uchun
    related_operation = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_pair', verbose_name="Bog'liq amaliyot (Ko'chirish)")

    class Meta:
        verbose_name = "Ombor Amaliyoti"
        verbose_name_plural = "Ombor Amaliyotlari"
        ordering = ['-timestamp']

    def clean(self):
        """Ma'lumotlar validatsiyasi"""
        if self.operation_type in [self.OperationType.ADD, self.OperationType.TRANSFER_IN, self.OperationType.RETURN, self.OperationType.INITIAL]:
            if self.quantity <= 0: # 0 ham mantiqsiz
                raise ValidationError({'quantity': "Kirim amaliyotlarida miqdor musbat bo'lishi kerak."})
        elif self.operation_type in [self.OperationType.REMOVE, self.OperationType.TRANSFER_OUT, self.OperationType.SALE]:
             if self.quantity >= 0: # 0 ham mantiqsiz
                 raise ValidationError({'quantity': "Chiqim amaliyotlarida miqdor manfiy bo'lishi kerak."})
        # Ko'chirishda related_operation bo'lishi kerak (lekin bu save() da hal qilinadi)

    def __str__(self):
        user_str = self.user.username if self.user else "Tizim"
        return f"{self.get_operation_type_display()} [{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {self.product.name} ({self.quantity}) @ {self.kassa.name} by {user_str}"