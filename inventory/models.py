# inventory/models.py
from decimal import Decimal

from django.db import models
from django.conf import settings # User uchun
from products.models import Product, Kassa # Bog'liqlik uchun
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from sales.models import Sale

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


class Supplier(models.Model):
    """Mahsulot Yetkazib Beruvchilar"""
    name = models.CharField(max_length=255, verbose_name="Yetkazib beruvchi nomi/ismi")
    phone_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefon raqami")
    address = models.TextField(blank=True, null=True, verbose_name="Manzili")
    contact_person = models.CharField(max_length=255, blank=True, null=True, verbose_name="Bog'lanish uchun shaxs")

    # store = models.ForeignKey(Store, ...) # Agar multi-tenant bo'lsa, lekin biz olib tashladik

    class Meta:
        verbose_name = "Yetkazib Beruvchi"
        verbose_name_plural = "Yetkazib Beruvchilar"
        ordering = ['name']

    def __str__(self):
        return self.name


class PurchaseOrder(models.Model):
    """Mahsulot Xarid Qilish Operatsiyasi"""

    class PurchasePaymentMethod(models.TextChoices):
        CASH = 'CASH', 'Naqd'
        BANK_TRANSFER = 'TRANSFER', 'Bank O\'tkazmasi'
        CREDIT_LINE = 'CREDIT', 'Nasiya (Yetkazib beruvchidan)'
        # Agar "Kredit" deganda bank krediti nazarda tutilsa, bu boshqacha yondashuv talab qiladi.
        # Hozircha "Nasiya" deb tushunamiz.

    payment_method = models.CharField(
        max_length=20,
        choices=PurchasePaymentMethod.choices,
        default=PurchasePaymentMethod.CREDIT_LINE,  # Yoki boshqa default
        verbose_name="Xarid To'lov Usuli"
    )

    class PurchaseStatus(models.TextChoices):
        PENDING = 'Pending', 'Kutilmoqda'  # Buyurtma berildi, lekin hali kelmadi
        PARTIALLY_RECEIVED = 'Partially Received', 'Qisman Qabul Qilindi'
        RECEIVED = 'Received', 'To\'liq Qabul Qilindi'
        CANCELLED = 'Cancelled', 'Bekor Qilingan'

    class PaymentStatus(models.TextChoices):
        UNPAID = 'Unpaid', 'To\'lanmagan'
        PARTIALLY_PAID = 'Partially Paid', 'Qisman To\'langan'
        PAID = 'Paid', 'To\'liq To\'langan'

    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='purchase_orders', verbose_name="Yetkazib Beruvchi")
    order_date = models.DateTimeField(default=timezone.now, verbose_name="Xarid Sanasi")

    # Xarid qaysi valyutada amalga oshirilgani
    # Sale modelidagi SaleCurrency ni ishlatsak bo'ladi yoki alohida yaratamiz
     # Agar sales.models da bo'lsa
    currency_choices = models.CharField(max_length=3, choices=Sale.SaleCurrency.choices, default=Sale.SaleCurrency.UZS, verbose_name="Xarid Valyutasi")
    # Yoki sodda CharField:
    # currency_choices = [('UZS', 'O\'zbek so\'mi'), ('USD', 'AQSH dollari')]
    # currency = models.CharField(max_length=3, choices=currency_choices, default='UZS', verbose_name="Xarid Valyutasi")

    total_amount = models.DecimalField(max_digits=17, decimal_places=2, default=Decimal(0),
                                       verbose_name="Umumiy Xarid Summasi (xarid valyutasida)")
    amount_paid = models.DecimalField(max_digits=17, decimal_places=2, default=Decimal(0),
                                      verbose_name="To'langan Summa (xarid valyutasida)")

    status = models.CharField(max_length=20, choices=PurchaseStatus.choices, default=PurchaseStatus.PENDING,
                              verbose_name="Xarid Holati")
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID,
                                      verbose_name="To'lov Holati")

    due_date_for_remaining = models.DateField(null=True, blank=True, verbose_name="Qolgan To'lov Sanasi")
    notes = models.TextField(blank=True, null=True, verbose_name="Izohlar")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   related_name='created_purchase_orders', verbose_name="Yaratgan Xodim")

    class Meta:
        verbose_name = "Xarid Operatsiyasi"
        verbose_name_plural = "Xarid Operatsiyalari"
        ordering = ['-order_date']

    def __str__(self):
        supplier_name_str = "Noma'lum Yetkazib Beruvchi"  # Default qiymat
        if self.supplier and self.supplier.name:
            supplier_name_str = self.supplier.name

        order_date_str = ""
        if self.order_date:
            order_date_str = self.order_date.strftime('%Y-%m-%d')

        return f"Xarid #{self.id} - {supplier_name_str} - {order_date_str}"

    @property
    def remaining_amount_to_pay(self):
        return max(self.total_amount - self.amount_paid, Decimal(0))

    def update_payment_status(self, force_save=False):
        if self.remaining_amount_to_pay <= Decimal('0.01'):
            self.payment_status = self.PaymentStatus.PAID
        elif self.amount_paid > Decimal(0) and self.amount_paid < self.total_amount:
            self.payment_status = self.PaymentStatus.PARTIALLY_PAID
        else:
            self.payment_status = self.PaymentStatus.UNPAID
        if force_save:
            self.save(update_fields=['payment_status'])


class PurchaseOrderItem(models.Model):
    """Xarid Operatsiyasidagi Har Bir Mahsulot"""
    purchase_order = models.ForeignKey(PurchaseOrder, related_name='items', on_delete=models.CASCADE,
                                       verbose_name="Xarid Operatsiyasi")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='purchase_items',
                                verbose_name="Mahsulot")
    quantity_ordered = models.PositiveIntegerField(validators=[MinValueValidator(1)],
                                                   verbose_name="Buyurtma Qilingan Miqdor")
    # Bu mahsulot omborga qabul qilingan miqdori (qisman qabul qilish uchun)
    quantity_received = models.PositiveIntegerField(default=0, verbose_name="Qabul Qilingan Miqdor")

    # Xarid narxi (har bir dona uchun, xarid valyutasida)
    purchase_price_currency = models.DecimalField(max_digits=17, decimal_places=2,
                                                  verbose_name="Xarid Narxi (bir dona uchun, xarid valyutasida)")
    # Agar mahsulotning UZS va USD narxlarini alohida saqlamoqchi bo'lsak (Product modelidagi kabi)
    # purchase_price_usd = models.DecimalField(...)
    # purchase_price_uzs = models.DecimalField(...)

    # Kassa - mahsulot qaysi kassaga kirim qilinishi kerak
    target_kassa = models.ForeignKey(Kassa, on_delete=models.PROTECT, related_name='incoming_purchase_items',
                                     verbose_name="Maqsadli Kassa/Ombor")

    class Meta:
        verbose_name = "Xarid Elementi"
        verbose_name_plural = "Xarid Elementlari"
        unique_together = (
        'purchase_order', 'product', 'target_kassa')  # Bir xaridda, bir mahsulot bir kassaga faqat bir marta

    def __str__(self):
        return f"{self.quantity_ordered} x {self.product.name} (Xarid #{self.purchase_order_id})"

    @property
    def item_total_amount(self):
        return self.quantity_ordered * self.purchase_price_currency

    @property
    def quantity_pending_receive(self):
        return self.quantity_ordered - self.quantity_received