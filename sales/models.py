# # sales/models.py
# from decimal import Decimal
#
# from django.db import models
# from django.conf import settings
# from products.models import Product, Kassa
# from django.core.validators import MinValueValidator
# from django.utils import timezone
#
#
#
#
# class Customer(models.Model):
#     # Bu model o'zgarishsiz qoladi
#     full_name = models.CharField(max_length=255, verbose_name="To'liq ismi")
#     phone_number = models.CharField(max_length=20, unique=True, verbose_name="Telefon raqami")
#     email = models.EmailField(blank=True, null=True, verbose_name="Email (ixtiyoriy)")
#     address = models.TextField(blank=True, null=True, verbose_name="Manzil (ixtiyoriy)")
#     created_at = models.DateTimeField(default=timezone.now, verbose_name="Qo'shilgan sana")
#
#     class Meta:
#         verbose_name = "Mijoz"
#         verbose_name_plural = "Mijozlar"
#         ordering = ['full_name']
#
#     def __str__(self):
#         return f"{self.full_name} ({self.phone_number})"
#
#
# class Sale(models.Model):
#     class PaymentType(models.TextChoices):
#         CASH = 'Naqd', 'Naqd'
#         CARD = 'Karta', 'Karta'
#         INSTALLMENT = 'Nasiya', 'Nasiya'
#
#     class SaleStatus(models.TextChoices):
#         COMPLETED = 'Completed', 'Yakunlangan'
#         RETURNED = 'Returned', 'Qaytarilgan'
#         PARTIALLY_RETURNED = 'Partially Returned', 'Qisman Qaytarilgan'
#         PENDING = 'Pending', 'Kutilmoqda'
#         CANCELLED = 'Cancelled', 'Bekor qilingan'
#
#     class SaleCurrency(models.TextChoices):
#         UZS = 'UZS', 'O\'zbek so\'mi'
#         USD = 'USD', 'AQSH dollari'
#
#     seller = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sales_conducted', on_delete=models.SET_NULL,
#                                null=True, verbose_name="Sotuvchi")
#     customer = models.ForeignKey(Customer, related_name='purchases', on_delete=models.SET_NULL, null=True, blank=True,
#                                  verbose_name="Mijoz")
#     kassa = models.ForeignKey(Kassa, related_name='sales_registered', on_delete=models.PROTECT,
#                               verbose_name="Kassa/Filial")
#
#     currency = models.CharField(max_length=3, choices=SaleCurrency.choices, default=SaleCurrency.UZS,
#                                 verbose_name="Sotuv Valyutasi")
#
#     # Mahsulotlarning katalogdagi narxlari bo'yicha jami summasi (chegirmasiz)
#     original_total_amount_currency = models.DecimalField(
#         max_digits=17, decimal_places=2, default=Decimal(0),
#         verbose_name="Asl Jami Summa (sotuv valyutasida, chegirmasiz)"
#     )
#
#     # Mijoz haqiqatda to'lashi kerak bo'lgan/to'lagan yakuniy summa (chegirma bilan)
#     # Nasiya uchun bu nasiyaning asosiy qarz summasi bo'ladi (foizsiz).
#     final_amount_currency = models.DecimalField(
#         max_digits=17, decimal_places=2, default=Decimal(0),
#         verbose_name="Yakuniy Summa (sotuv valyutasida, chegirma bilan)"
#     )
#
#     # Sotuv paytida kassaga haqiqatda tushgan pul
#     # Naqd/Karta uchun bu final_amount_currency ga teng.
#     # Nasiya uchun bu boshlang'ich to'lov (down_payment) ga teng.
#     amount_actually_paid_at_sale = models.DecimalField(
#         max_digits=17, decimal_places=2, default=Decimal(0),
#         verbose_name="Sotuv Paytida Haqiqatda To'langan (sotuv valyutasida)"
#     )
#
#     payment_type = models.CharField(max_length=10, choices=PaymentType.choices, verbose_name="To'lov turi")
#     status = models.CharField(max_length=20, choices=SaleStatus.choices, default=SaleStatus.COMPLETED,
#                               verbose_name="Holati")
#     created_at = models.DateTimeField(default=timezone.now, verbose_name="Sana va vaqt")
#
#     # Eski total_amount_usd, total_amount_uzs, amount_paid_uzs maydonlari olib tashlandi
#
#     class Meta:
#         verbose_name = "Sotuv"
#         verbose_name_plural = "Sotuvlar"
#         ordering = ['-created_at']
#
#     def __str__(self):
#         customer_name = self.customer.full_name if self.customer else "Noma'lum mijoz"
#         return f"Sotuv #{self.id} ({customer_name}) - Yakuniy: {self.final_amount_currency} {self.currency}"
#
#     @property
#     def can_be_returned(self):
#         return self.status in [self.SaleStatus.COMPLETED, self.SaleStatus.PARTIALLY_RETURNED]
#
#     @property
#     def discount_amount_currency(self):
#         return self.original_total_amount_currency - self.final_amount_currency
#
#
# class SaleItem(models.Model):
#     sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE, verbose_name="Sotuv")
#     product = models.ForeignKey(Product, related_name='sale_items', on_delete=models.PROTECT, verbose_name="Mahsulot")
#     quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Miqdori")
#
#     # Sotuv paytidagi narx (bu mijozga sotilgan yakuniy narx, chegirma bilan)
#     price_at_sale_currency = models.DecimalField(
#         max_digits=17, decimal_places=2,
#         verbose_name="Sotilgan Narx (bir dona uchun, sotuv valyutasida)"
#     )
#     # original_price_at_sale_usd/uzs (mahsulotning katalogdagi narxini saqlash uchun)
#     original_price_at_sale_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
#                                                      verbose_name="Asl Narx (USD)")
#     original_price_at_sale_uzs = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True,
#                                                      verbose_name="Asl Narx (UZS)")
#
#     quantity_returned = models.PositiveIntegerField(default=0, verbose_name="Qaytarilgan miqdor")
#
#
#
#     class Meta:
#         unique_together = ('sale', 'product')
#         verbose_name = "Sotuv Elementi"
#         verbose_name_plural = "Sotuv Elementlari"
#
#     @property
#     def item_total_final_currency(self):
#         """Elementning yakuniy summasi (sotuv valyutasida)"""
#         return self.quantity * self.price_at_sale_currency
#
#     @property
#     def quantity_available_to_return(self):
#         return self.quantity - self.quantity_returned
#
#
# class SaleItem(models.Model):
#     sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE, verbose_name="Sotuv")
#     product = models.ForeignKey(Product, related_name='sale_items', on_delete=models.PROTECT, verbose_name="Mahsulot")
#     quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Miqdori")
#     # Sotuv paytidagi narxlarni ikkala valyutada ham saqlash foydali
#     price_at_sale_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Narx (USD) (sotuv paytida)")
#     price_at_sale_uzs = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Narx (UZS) (sotuv paytida)")
#     quantity_returned = models.PositiveIntegerField(default=0, verbose_name="Qaytarilgan miqdor")
#
#     class Meta:
#          unique_together = ('sale', 'product')
#          verbose_name = "Sotuv Elementi"
#          verbose_name_plural = "Sotuv Elementlari"
#
#     def __str__(self):
#         return f"{self.quantity} x {self.product.name} (Sotuv #{self.sale.id})"
#
#     @property
#     def item_total_in_sale_currency(self):
#         """Elementning umumiy summasi (sotuvning asosiy valyutasida)"""
#         if self.sale.currency == Sale.SaleCurrency.UZS:
#             price = self.price_at_sale_uzs or Decimal(0)
#         elif self.sale.currency == Sale.SaleCurrency.USD:
#             price = self.price_at_sale_usd or Decimal(0)
#         else:
#             return Decimal(0) # Noma'lum valyuta
#         return self.quantity * price
#
#     @property
#     def quantity_available_to_return(self):
#          return self.quantity - self.quantity_returned
#
# class SaleReturn(models.Model):
#     """Sotuvni qaytarish operatsiyasi"""
#     original_sale = models.ForeignKey(
#         Sale,
#         related_name='returns',
#         on_delete=models.CASCADE, # Asosiy sotuv o'chsa, qaytarish ham o'chadi
#         verbose_name="Asl Sotuv"
#     )
#     reason = models.TextField(blank=True, null=True, verbose_name="Qaytarish sababi")
#     returned_by = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.SET_NULL,
#         null=True, # Kim qaytargani noma'lum bo'lishi mumkin
#         verbose_name="Qaytaruvchi Xodim"
#     )
#     created_at = models.DateTimeField(default=timezone.now, verbose_name="Qaytarilgan sana")
#     # Qaytarilgan umumiy summa (hisoblangan)
#     total_returned_amount_uzs = models.DecimalField(
#         max_digits=17, decimal_places=2, default=0,
#         verbose_name="Jami qaytarilgan summa (UZS)"
#     )
#
#     class Meta:
#         verbose_name = "Sotuv Qaytarish"
#         verbose_name_plural = "Sotuv Qaytarishlar"
#         ordering = ['-created_at']
#
#     def __str__(self):
#         return f"Qaytarish #{self.id} (Sotuv #{self.original_sale_id}) - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
#
# class KassaTransaction(models.Model):
#     """Kassadagi pul harakati (kirim/chiqim)"""
#     class TransactionType(models.TextChoices):
#         SALE = 'SALE', 'Sotuvdan Kirim'
#         INSTALLMENT_PAYMENT = 'INSTALLMENT', 'Nasiyadan Kirim'
#         CASH_IN = 'CASH_IN', 'Kirim (Boshqa)' # Masalan, kassaga pul qo'yish
#         CASH_OUT = 'CASH_OUT', 'Chiqim (Xarajat)' # Masalan, xarajatlar
#         RETURN_REFUND = 'REFUND', 'Qaytarish (Chiqim)' # Mijozga pul qaytarilganda
#
#
#     kassa = models.ForeignKey(Kassa, on_delete=models.PROTECT, related_name='transactions', verbose_name="Kassa")
#     # Summa har doim musbat, turi kirim/chiqimligini belgilaydi
#     amount = models.DecimalField(max_digits=17, decimal_places=2, verbose_name="Summa (UZS)")
#     transaction_type = models.CharField(max_length=20, choices=TransactionType.choices, verbose_name="Amaliyot Turi")
#     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Xodim")
#     comment = models.TextField(blank=True, null=True, verbose_name="Izoh")
#     # Qaysi sotuv, to'lov yoki qaytarishga bog'liqligi (ixtiyoriy)
#     related_sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name='kassa_transactions')
#     related_installment_payment = models.ForeignKey('installments.InstallmentPayment', on_delete=models.SET_NULL, null=True, blank=True, related_name='kassa_transactions')
#     related_return = models.ForeignKey(SaleReturn, on_delete=models.SET_NULL, null=True, blank=True, related_name='kassa_transactions')
#     timestamp = models.DateTimeField(default=timezone.now, verbose_name="Sana va Vaqt")
#
#     class Meta:
#         verbose_name = "Kassa Amaliyoti"
#         verbose_name_plural = "Kassa Amaliyotlari"
#         ordering = ['-timestamp']
#
#     def __str__(self):
#         sign = "+" if self.transaction_type in [self.TransactionType.SALE, self.TransactionType.INSTALLMENT_PAYMENT, self.TransactionType.CASH_IN] else "-"
#         return f"{self.kassa.name}: {sign}{self.amount} UZS ({self.get_transaction_type_display()}) - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
#
# class SaleReturnItem(models.Model):
#      """Qaytarilgan sotuv tarkibidagi element"""
#      sale_return = models.ForeignKey(
#          SaleReturn,
#          related_name='items',
#          on_delete=models.CASCADE, # Qaytarish operatsiyasi o'chsa, bu ham o'chadi
#          verbose_name="Qaytarish Operatsiyasi"
#      )
#      # Qaysi sotuv elementi qaytarildi
#      sale_item = models.ForeignKey(
#          SaleItem,
#          on_delete=models.CASCADE, # Element o'chsa... (balki PROTECT?)
#          verbose_name="Asl Sotuv Elementi"
#      )
#      # Shu operatsiyada qancha qaytarildi
#      quantity_returned = models.PositiveIntegerField(verbose_name="Qaytarilgan miqdor (shu operatsiyada)")
#
#      class Meta:
#          verbose_name = "Qaytarilgan Element"
#          verbose_name_plural = "Qaytarilgan Elementlar"
#
#      def __str__(self):
#          return f"{self.quantity_returned} dona {self.sale_item.product.name} (Qaytarish #{self.sale_return.id})"


# sales/models.py
from decimal import Decimal
from django.db import models
from django.conf import settings
from products.models import Product, Kassa
from django.core.validators import MinValueValidator
from django.utils import timezone


# installments.models import InstallmentPayment # KassaTransaction da to'g'ridan-to'g'ri bog'liqlik bor


class Customer(models.Model):
    # ... (o'zgarishsiz)
    full_name = models.CharField(max_length=255, verbose_name="To'liq ismi")
    phone_number = models.CharField(max_length=20, unique=True, verbose_name="Telefon raqami")
    email = models.EmailField(blank=True, null=True, verbose_name="Email (ixtiyoriy)")
    address = models.TextField(blank=True, null=True, verbose_name="Manzil (ixtiyoriy)")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Qo'shilgan sana")

    class Meta: verbose_name = "Mijoz"; verbose_name_plural = "Mijozlar"; ordering = ['full_name']

    def __str__(self): return f"{self.full_name} ({self.phone_number})"


class Sale(models.Model):
    class PaymentType(
        models.TextChoices): CASH = 'Naqd', 'Naqd'; CARD = 'Karta', 'Karta'; INSTALLMENT = 'Nasiya', 'Nasiya'

    class SaleStatus(
        models.TextChoices): COMPLETED = 'Completed', 'Yakunlangan'; RETURNED = 'Returned', 'Qaytarilgan'; PARTIALLY_RETURNED = 'Partially Returned', 'Qisman Qaytarilgan'; PENDING = 'Pending', 'Kutilmoqda'; CANCELLED = 'Cancelled', 'Bekor qilingan'

    class SaleCurrency(models.TextChoices): UZS = 'UZS', 'O\'zbek so\'mi'; USD = 'USD', 'AQSH dollari'

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sales_conducted', on_delete=models.SET_NULL,
                               null=True, verbose_name="Sotuvchi")
    customer = models.ForeignKey(Customer, related_name='purchases', on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name="Mijoz")
    kassa = models.ForeignKey(Kassa, related_name='sales_registered', on_delete=models.PROTECT,
                              verbose_name="Kassa/Filial")
    currency = models.CharField(max_length=3, choices=SaleCurrency.choices, default=SaleCurrency.UZS,
                                verbose_name="Sotuv Valyutasi")
    original_total_amount_currency = models.DecimalField(max_digits=17, decimal_places=2, default=Decimal(0),
                                                         verbose_name="Asl Jami Summa (sotuv valyutasida, chegirmasiz)")
    final_amount_currency = models.DecimalField(max_digits=17, decimal_places=2, default=Decimal(0),
                                                verbose_name="Yakuniy Summa (sotuv valyutasida, chegirma bilan)")
    amount_actually_paid_at_sale = models.DecimalField(max_digits=17, decimal_places=2, default=Decimal(0),
                                                       verbose_name="Sotuv Paytida Haqiqatda To'langan (sotuv valyutasida)")
    payment_type = models.CharField(max_length=10, choices=PaymentType.choices, verbose_name="To'lov turi")
    status = models.CharField(max_length=20, choices=SaleStatus.choices, default=SaleStatus.COMPLETED,
                              verbose_name="Holati")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Sana va vaqt")

    class Meta: verbose_name = "Sotuv"; verbose_name_plural = "Sotuvlar"; ordering = ['-created_at']

    def __str__(
            self): customer_name = self.customer.full_name if self.customer else "Noma'lum mijoz"; return f"Sotuv #{self.id} ({customer_name}) - Yakuniy: {self.final_amount_currency} {self.currency}"

    @property
    def can_be_returned(self): return self.status in [self.SaleStatus.COMPLETED, self.SaleStatus.PARTIALLY_RETURNED]

    @property
    def discount_amount_currency(self): return self.original_total_amount_currency - self.final_amount_currency


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE, verbose_name="Sotuv")
    product = models.ForeignKey(Product, related_name='sale_items', on_delete=models.PROTECT, verbose_name="Mahsulot")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Miqdori")
    price_at_sale_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                            verbose_name="Narx (USD) (sotuv paytida)")
    price_at_sale_uzs = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True,
                                            verbose_name="Narx (UZS) (sotuv paytida)")
    quantity_returned = models.PositiveIntegerField(default=0, verbose_name="Qaytarilgan miqdor")
    # original_price_at_sale_usd/uzs (Sale modelidagi kabi SaleItem da ham saqlanishi mumkin)
    original_price_at_sale_usd_item = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                                          verbose_name="Asl Narx (USD) (element uchun)")  # O'ZGARTIRILDI: Nomini aniqlashtirish
    original_price_at_sale_uzs_item = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True,
                                                          verbose_name="Asl Narx (UZS) (element uchun)")  # O'ZGARTIRILDI: Nomini aniqlashtirish

    class Meta:
        unique_together = (
        'sale', 'product'); verbose_name = "Sotuv Elementi"; verbose_name_plural = "Sotuv Elementlari"

    def __str__(self):
        return f"{self.quantity} x {self.product.name} (Sotuv #{self.sale.id})"

    @property
    def item_total_in_sale_currency(self):
        if self.sale.currency == Sale.SaleCurrency.UZS:
            price = self.price_at_sale_uzs or Decimal(0)
        elif self.sale.currency == Sale.SaleCurrency.USD:
            price = self.price_at_sale_usd or Decimal(0)
        else:
            return Decimal(0)
        return self.quantity * price

    @property
    def quantity_available_to_return(self):
        return self.quantity - self.quantity_returned


class SaleReturn(models.Model):
    """Sotuvni qaytarish operatsiyasi"""
    original_sale = models.ForeignKey(Sale, related_name='returns', on_delete=models.CASCADE, verbose_name="Asl Sotuv")
    reason = models.TextField(blank=True, null=True, verbose_name="Qaytarish sababi")
    returned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    verbose_name="Qaytaruvchi Xodim")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Qaytarilgan sana")

    # O'ZGARTIRILDI: Qaytarilgan summa va valyutasi
    returned_amount_currency_value = models.DecimalField(  # Nomini o'zgartirdim
        max_digits=17, decimal_places=2, default=Decimal(0),
        verbose_name="Jami qaytarilgan summa (qaytarish valyutasida)"
    )
    currency_of_return = models.CharField(  # Qaysi valyutada qaytarilgani
        max_length=3, choices=Sale.SaleCurrency.choices,
        default=Sale.SaleCurrency.UZS,  # Yoki original_sale.currency ga qarab
        verbose_name="Qaytarish Valyutasi"
    )

    class Meta: verbose_name = "Sotuv Qaytarish"; verbose_name_plural = "Sotuv Qaytarishlar"; ordering = ['-created_at']

    def __str__(
            self): return f"Qaytarish #{self.id} (Sotuv #{self.original_sale_id}) - {self.returned_amount_currency_value} {self.currency_of_return}"


class KassaTransaction(models.Model):
    """Kassadagi pul harakati (kirim/chiqim)"""

    class TransactionType(models.TextChoices):
        SALE = 'SALE', 'Sotuvdan Kirim'
        INSTALLMENT_PAYMENT = 'INSTALLMENT', 'Nasiyadan Kirim'
        CASH_IN = 'CASH_IN', 'Kirim (Boshqa)'
        CASH_OUT = 'CASH_OUT', 'Chiqim (Xarajat)'
        RETURN_REFUND = 'REFUND', 'Qaytarish (Chiqim)'
        # YANGI QO'SHILDI: Valyuta ayirboshlash uchun
        EXCHANGE_SELL_CURRENCY = 'EXCHANGE_SELL', 'Valyuta Sotish (Chiqim)'  # Masalan, USD sotib UZS olish (USD chiqim)
        EXCHANGE_BUY_CURRENCY = 'EXCHANGE_BUY', 'Valyuta Olish (Kirim)'  # Masalan, UZS berib USD olish (USD kirim)

    kassa = models.ForeignKey(Kassa, on_delete=models.PROTECT, related_name='transactions', verbose_name="Kassa")

    # O'ZGARTIRILGAN QISM (avvalgi javobdagidek)
    currency = models.CharField(
        max_length=3,
        choices=Sale.SaleCurrency.choices,
        default=Sale.SaleCurrency.UZS,
        verbose_name="Amaliyot Valyutasi"
    )
    amount = models.DecimalField(max_digits=17, decimal_places=2, verbose_name="Summa (amaliyot valyutasida)")
    # --- O'ZGARTIRILGAN QISM TUGADI ---

    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices,
                                        verbose_name="Amaliyot Turi")  # max_length ni EXCHANGE_... uchun yetarli qilish kerak bo'lsa, oshiring
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             verbose_name="Xodim")
    comment = models.TextField(blank=True, null=True, verbose_name="Izoh")
    related_sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='kassa_transactions')
    related_installment_payment = models.ForeignKey('installments.InstallmentPayment', on_delete=models.SET_NULL,
                                                    null=True, blank=True, related_name='kassa_transactions')
    related_return = models.ForeignKey(SaleReturn, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='kassa_transactions')
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="Sana va Vaqt")

    class Meta: verbose_name = "Kassa Amaliyoti"; verbose_name_plural = "Kassa Amaliyotlari"; ordering = ['-timestamp']

    def __str__(self):
        # Kirim/Chiqim turlarini aniqlash uchun ro'yxatlar
        income_op_types = [self.TransactionType.SALE, self.TransactionType.INSTALLMENT_PAYMENT,
                           self.TransactionType.CASH_IN, self.TransactionType.EXCHANGE_BUY_CURRENCY]
        # EXCHANGE_SELL_CURRENCY bu yerda chiqim, chunki sotilayotgan valyuta kassadan chiqadi
        expense_op_types = [self.TransactionType.CASH_OUT, self.TransactionType.RETURN_REFUND,
                            self.TransactionType.EXCHANGE_SELL_CURRENCY]

        sign = "+" if self.transaction_type in income_op_types else "-"
        if self.transaction_type not in income_op_types and self.transaction_type not in expense_op_types:
            sign = "?"  # Noma'lum operatsiya turi uchun

        return f"{self.kassa.name}: {sign}{self.amount} {self.currency} ({self.get_transaction_type_display()}) - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class SaleReturnItem(models.Model):
    sale_return = models.ForeignKey(SaleReturn, related_name='items', on_delete=models.CASCADE,
                                    verbose_name="Qaytarish Operatsiyasi")
    sale_item = models.ForeignKey(SaleItem, on_delete=models.CASCADE, verbose_name="Asl Sotuv Elementi")
    quantity_returned = models.PositiveIntegerField(verbose_name="Qaytarilgan miqdor (shu operatsiyada)")

    class Meta: verbose_name = "Qaytarilgan Element"; verbose_name_plural = "Qaytarilgan Elementlar"

    def __str__(
            self): return f"{self.quantity_returned} dona {self.sale_item.product.name} (Qaytarish #{self.sale_return.id})"