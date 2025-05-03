# installments/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from sales.models import Sale, Customer # Bog'liqlik
from users.models import Store


class InstallmentPlan(models.Model):
    """Nasiya shartnomasi"""
    store = models.ForeignKey(Store, related_name='installment_plans', on_delete=models.CASCADE, verbose_name="Do'kon")
    class PlanStatus(models.TextChoices):
        ACTIVE = 'Active', 'Faol'
        PAID = 'Paid', 'Yakunlangan'
        OVERDUE = 'Overdue', 'Kechikkan' # To'lov muddati o'tgan
        CANCELLED = 'Cancelled', 'Bekor qilingan' # Sotuv qaytarilganda

    # Sotuvga OneToOne bog'liqlik
    sale = models.OneToOneField(
        Sale,
        on_delete=models.CASCADE, # Sotuv o'chsa, nasiya ham o'chadi
        related_name='installmentplan',
        verbose_name="Asosiy Sotuv"
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT, # Mijoz o'chsa nasiya qolishi kerak (balki?)
        related_name='installment_plans',
        verbose_name="Mijoz"
    )
    total_due = models.DecimalField(max_digits=17, decimal_places=2, verbose_name="Umumiy qarz (UZS)")
    amount_paid = models.DecimalField(max_digits=17, decimal_places=2, default=0, verbose_name="Jami to'langan (UZS)")
    # To'lov grafigi uchun soddalashtirilgan variant: keyingi to'lov sanasi
    # Batafsil grafik uchun alohida model kerak bo'lishi mumkin
    next_payment_date = models.DateField(null=True, blank=True, verbose_name="Keyingi to'lov sanasi")
    # Boshqa shartlar (masalan, oylik to'lov miqdori) qo'shilishi mumkin
    # payment_per_period = models.DecimalField(...)
    # period_type = models.CharField(choices=[('Month', 'Oy'), ('Week', 'Hafta')], ...)
    status = models.CharField(max_length=10, choices=PlanStatus.choices, default=PlanStatus.ACTIVE, verbose_name="Holati")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Yaratilgan sana")
    # Sotuv qaytarilganda o'zgarishi mumkin
    return_adjustment = models.DecimalField(max_digits=17, decimal_places=2, default=0, verbose_name="Qaytarish tuzatishi (UZS)")

    class Meta:
        verbose_name = "Nasiya Rejasi"
        verbose_name_plural = "Nasiya Rejalari"
        ordering = ['-created_at']

    @property
    def remaining_amount(self):
        """Qolgan qarz miqdori"""
        # Qaytarishni hisobga olish
        remaining = self.total_due - self.return_adjustment - self.amount_paid
        return max(remaining, 0) # Manfiy bo'lmasligi kerak

    @property
    def is_overdue(self):
        """To'lov muddati o'tganligini tekshirish"""
        return (
            self.status != self.PlanStatus.PAID and
            self.status != self.PlanStatus.CANCELLED and
            self.next_payment_date and
            self.next_payment_date < timezone.now().date()
        )

    def update_status(self, force_save=False):
        """Nasiya holatini avtomatik yangilaydi"""
        if self.status == self.PlanStatus.CANCELLED:
            return # O'zgarmaydi

        if self.remaining_amount <= 0:
            self.status = self.PlanStatus.PAID
            self.next_payment_date = None # Yakunlangan bo'lsa keyingi sana yo'q
        elif self.is_overdue:
            self.status = self.PlanStatus.OVERDUE
        else:
             self.status = self.PlanStatus.ACTIVE

        if force_save:
             self.save(update_fields=['status', 'next_payment_date'])

    # Sotuv qaytarilganda chaqiriladigan metod
    def adjust_for_return(self, returned_amount_uzs):
        self.return_adjustment += returned_amount_uzs
        # Agar qaytarishdan keyin qarz qolmasa yoki manfiy bo'lsa, statusni o'zgartirish
        if self.remaining_amount <= 0:
            # Agar oldin to'langan summa qaytarilgan summadan ko'p bo'lsa,
            # mijozga pul qaytarish kerak bo'lishi mumkin (bu logikani alohida handle qilish kerak)
            refund_due = self.amount_paid - (self.total_due - self.return_adjustment)
            if refund_due > 0:
                 print(f"INFO: Refund of {refund_due} UZS may be due to customer for plan {self.id}")
            self.status = self.PlanStatus.PAID # Yoki CANCELLED?
            self.next_payment_date = None
        else:
             self.update_status() # Statusni qayta tekshirish
        # Bu metoddan keyin .save() chaqirilishi kerak

    def __str__(self):
        return f"Nasiya #{self.id} (Sotuv #{self.sale_id}) - {self.customer.full_name} ({self.get_status_display()})"

class InstallmentPayment(models.Model):
    """Nasiya bo'yicha qilingan to'lov"""
    class PaymentMethod(models.TextChoices):
        CASH = 'Naqd', 'Naqd'
        CARD = 'Karta', 'Karta'
        TRANSFER = 'O\'tkazma', 'O\'tkazma'

    plan = models.ForeignKey(InstallmentPlan, related_name='payments', on_delete=models.CASCADE, verbose_name="Nasiya Rejasi")
    amount = models.DecimalField(max_digits=17, decimal_places=2, verbose_name="To'lov summasi (UZS)")
    payment_date = models.DateTimeField(default=timezone.now, verbose_name="To'lov sanasi")
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CASH, verbose_name="To'lov usuli")
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Qabul qilgan xodim")

    class Meta:
        verbose_name = "Nasiya To'lovi"
        verbose_name_plural = "Nasiya To'lovlari"
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.amount} UZS to'lov (Reja #{self.plan_id}) - {self.payment_date.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
         # Yangi to'lov qo'shilganda Plan ni yangilash kerak emas,
         # chunki Plan amount_paid alohida yangilanadi (serializerda).
         # Faqat Plan.update_status() ni chaqirish mumkin.
         super().save(*args, **kwargs)

# Signal orqali to'lovdan keyin Plan statusini yangilash (yoki serializerda qilish)
# @receiver(post_save, sender=InstallmentPayment)
# def update_plan_status_on_payment(sender, instance, created, **kwargs):
#     if created:
#         instance.plan.update_status(force_save=True)