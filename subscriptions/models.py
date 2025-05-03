# subscriptions/models.py
from django.db import models
from django.core.validators import MinValueValidator

class SubscriptionPlan(models.Model):
    """Obuna tarif rejasi"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Tarif Nomi")
    price_uzs = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(0)], verbose_name="Narxi (UZS)")
    # Limitlar (None - cheklanmagan degani)
    product_limit = models.PositiveIntegerField(null=True, blank=True, verbose_name="Mahsulot Limiti")
    branch_limit = models.PositiveIntegerField(null=True, blank=True, verbose_name="Filial (Kassa) Limiti")
    user_limit = models.PositiveIntegerField(null=True, blank=True, verbose_name="Xodim Limiti")
    # Qo'shimcha imkoniyatlar (Boolean)
    allow_installments = models.BooleanField(default=False, verbose_name="Nasiya Savdoga Ruxsat")
    allow_multi_currency = models.BooleanField(default=False, verbose_name="Ko'p Valyutali Tizim")
    # Boshqa imkoniyatlar...
    # description = models.TextField(blank=True, null=True, verbose_name="Tavsif")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv Tarif") # Superadmin faollashtirishi/o'chirishi mumkin

    class Meta:
        verbose_name = "Obuna Tarifi"
        verbose_name_plural = "Obuna Tariflari"
        ordering = ['price_uzs'] # Narxi bo'yicha tartiblash

    def __str__(self):
        return self.name