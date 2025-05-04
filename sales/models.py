# sales/models.py
from django.db import models
from django.conf import settings
from products.models import Product, Kassa
from django.core.validators import MinValueValidator
from django.utils import timezone




class Customer(models.Model):
    """Mijozlar ma'lumotlari"""
    full_name = models.CharField(max_length=255, verbose_name="To'liq ismi")
    # Telefon raqam majburiy va unikal bo'lishi yaxshi
    phone_number = models.CharField(max_length=20, unique=True, verbose_name="Telefon raqami")
    email = models.EmailField(blank=True, null=True, verbose_name="Email (ixtiyoriy)")
    address = models.TextField(blank=True, null=True, verbose_name="Manzil (ixtiyoriy)")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Qo'shilgan sana")

    class Meta:
        verbose_name = "Mijoz"
        verbose_name_plural = "Mijozlar"
        ordering = ['full_name']

    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"


class Sale(models.Model):
    """Sotuv operatsiyasi"""
    class PaymentType(models.TextChoices):
        CASH = 'Naqd', 'Naqd'
        CARD = 'Karta', 'Karta'
        INSTALLMENT = 'Nasiya', 'Nasiya'
        MIXED = 'Aralash', 'Aralash' # Hozircha faollashtirmaymiz

    class SaleStatus(models.TextChoices):
        COMPLETED = 'Completed', 'Yakunlangan'
        RETURNED = 'Returned', 'Qaytarilgan' # To'liq qaytarilgan
        PARTIALLY_RETURNED = 'Partially Returned', 'Qisman Qaytarilgan'
        PENDING = 'Pending', 'Kutilmoqda' # Kam ishlatiladi, lekin imkoniyat
        CANCELLED = 'Cancelled', 'Bekor qilingan' # To'lovgacha bekor qilish

    # Sotuvchi (tizimga kirgan foydalanuvchi)
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='sales_conducted', # related_name ni o'zgartirdik
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Sotuvchi"
    )
    # Mijoz (Nasiya uchun majburiy, boshqalar uchun ixtiyoriy)
    customer = models.ForeignKey(
        Customer,
        related_name='purchases',
        on_delete=models.SET_NULL,
        null=True, blank=True, # Naqd/Karta uchun ixtiyoriy
        verbose_name="Mijoz"
    )
    # Qaysi kassadan sotildi
    kassa = models.ForeignKey(
        Kassa,
        related_name='sales_registered', # related_name ni o'zgartirdik
        on_delete=models.PROTECT, # Kassa o'chirilsa sotuvlar qolishi kerak
        verbose_name="Kassa/Filial"
    )
    # Summalar (Hisoblangan qiymatlar)
    total_amount_usd = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Umumiy summa (USD)")
    total_amount_uzs = models.DecimalField(max_digits=17, decimal_places=2, default=0, verbose_name="Umumiy summa (UZS)")
    # To'lov ma'lumotlari
    payment_type = models.CharField(max_length=10, choices=PaymentType.choices, verbose_name="To'lov turi")
    amount_paid_uzs = models.DecimalField(
        max_digits=17, decimal_places=2, default=0,
        verbose_name="To'langan summa (UZS)",
        help_text="Aralash yoki Nasiya to'lovining boshlang'ich qismi"
    ) # Nasiya/Aralash uchun ishlatiladi
    # Holati va vaqti
    status = models.CharField(max_length=20, choices=SaleStatus.choices, default=SaleStatus.COMPLETED, verbose_name="Holati")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Sana va vaqt")

    class Meta:
        verbose_name = "Sotuv"
        verbose_name_plural = "Sotuvlar"
        ordering = ['-created_at']

    def __str__(self):
        customer_name = self.customer.full_name if self.customer else "Noma'lum mijoz"
        return f"Sotuv #{self.id} ({customer_name}) - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    # Qaytarish logikasi uchun xulosa (keyingi bosqichda to'ldiriladi)
    @property
    def can_be_returned(self):
         return self.status in [self.SaleStatus.COMPLETED, self.SaleStatus.PARTIALLY_RETURNED]


class SaleItem(models.Model):
    """Sotuv tarkibidagi mahsulot"""
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE, verbose_name="Sotuv")
    product = models.ForeignKey(Product, related_name='sale_items', on_delete=models.PROTECT, verbose_name="Mahsulot") # Mahsulot o'chsa ham tarix qolishi kerak
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Miqdori")
    # Sotuv paytidagi narxlarni saqlash muhim!
    price_at_sale_usd = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Narx (USD) (sotuv paytida)")
    price_at_sale_uzs = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Narx (UZS) (sotuv paytida)")
    # Qaytarish uchun (keyingi bosqich)
    quantity_returned = models.PositiveIntegerField(default=0, verbose_name="Qaytarilgan miqdor")

    class Meta:
         unique_together = ('sale', 'product') # Bir sotuvda bir mahsulot faqat bir marta bo'lishi kerak
         verbose_name = "Sotuv Elementi"
         verbose_name_plural = "Sotuv Elementlari"

    def __str__(self):
        return f"{self.quantity} x {self.product.name} (Sotuv #{self.sale.id})"

    @property
    def item_total_usd(self):
        """Elementning umumiy summasi (USD)"""
        return self.quantity * self.price_at_sale_usd

    @property
    def item_total_uzs(self):
        """Elementning umumiy summasi (UZS)"""
        return self.quantity * self.price_at_sale_uzs

    @property
    def quantity_available_to_return(self):
         """Qaytarish uchun mavjud miqdor"""
         return self.quantity - self.quantity_returned

class SaleReturn(models.Model):
    """Sotuvni qaytarish operatsiyasi"""
    original_sale = models.ForeignKey(
        Sale,
        related_name='returns',
        on_delete=models.CASCADE, # Asosiy sotuv o'chsa, qaytarish ham o'chadi
        verbose_name="Asl Sotuv"
    )
    reason = models.TextField(blank=True, null=True, verbose_name="Qaytarish sababi")
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, # Kim qaytargani noma'lum bo'lishi mumkin
        verbose_name="Qaytaruvchi Xodim"
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Qaytarilgan sana")
    # Qaytarilgan umumiy summa (hisoblangan)
    total_returned_amount_uzs = models.DecimalField(
        max_digits=17, decimal_places=2, default=0,
        verbose_name="Jami qaytarilgan summa (UZS)"
    )

    class Meta:
        verbose_name = "Sotuv Qaytarish"
        verbose_name_plural = "Sotuv Qaytarishlar"
        ordering = ['-created_at']

    def __str__(self):
        return f"Qaytarish #{self.id} (Sotuv #{self.original_sale_id}) - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class KassaTransaction(models.Model):
    """Kassadagi pul harakati (kirim/chiqim)"""
    class TransactionType(models.TextChoices):
        SALE = 'SALE', 'Sotuvdan Kirim'
        INSTALLMENT_PAYMENT = 'INSTALLMENT', 'Nasiyadan Kirim'
        CASH_IN = 'CASH_IN', 'Kirim (Boshqa)' # Masalan, kassaga pul qo'yish
        CASH_OUT = 'CASH_OUT', 'Chiqim (Xarajat)' # Masalan, xarajatlar
        RETURN_REFUND = 'REFUND', 'Qaytarish (Chiqim)' # Mijozga pul qaytarilganda


    kassa = models.ForeignKey(Kassa, on_delete=models.PROTECT, related_name='transactions', verbose_name="Kassa")
    # Summa har doim musbat, turi kirim/chiqimligini belgilaydi
    amount = models.DecimalField(max_digits=17, decimal_places=2, verbose_name="Summa (UZS)")
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices, verbose_name="Amaliyot Turi")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Xodim")
    comment = models.TextField(blank=True, null=True, verbose_name="Izoh")
    # Qaysi sotuv, to'lov yoki qaytarishga bog'liqligi (ixtiyoriy)
    related_sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name='kassa_transactions')
    related_installment_payment = models.ForeignKey('installments.InstallmentPayment', on_delete=models.SET_NULL, null=True, blank=True, related_name='kassa_transactions')
    related_return = models.ForeignKey(SaleReturn, on_delete=models.SET_NULL, null=True, blank=True, related_name='kassa_transactions')
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="Sana va Vaqt")

    class Meta:
        verbose_name = "Kassa Amaliyoti"
        verbose_name_plural = "Kassa Amaliyotlari"
        ordering = ['-timestamp']

    def __str__(self):
        sign = "+" if self.transaction_type in [self.TransactionType.SALE, self.TransactionType.INSTALLMENT_PAYMENT, self.TransactionType.CASH_IN] else "-"
        return f"{self.kassa.name}: {sign}{self.amount} UZS ({self.get_transaction_type_display()}) - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

class SaleReturnItem(models.Model):
     """Qaytarilgan sotuv tarkibidagi element"""
     sale_return = models.ForeignKey(
         SaleReturn,
         related_name='items',
         on_delete=models.CASCADE, # Qaytarish operatsiyasi o'chsa, bu ham o'chadi
         verbose_name="Qaytarish Operatsiyasi"
     )
     # Qaysi sotuv elementi qaytarildi
     sale_item = models.ForeignKey(
         SaleItem,
         on_delete=models.CASCADE, # Element o'chsa... (balki PROTECT?)
         verbose_name="Asl Sotuv Elementi"
     )
     # Shu operatsiyada qancha qaytarildi
     quantity_returned = models.PositiveIntegerField(verbose_name="Qaytarilgan miqdor (shu operatsiyada)")

     class Meta:
         verbose_name = "Qaytarilgan Element"
         verbose_name_plural = "Qaytarilgan Elementlar"

     def __str__(self):
         return f"{self.quantity_returned} dona {self.sale_item.product.name} (Qaytarish #{self.sale_return.id})"