# installments/models.py
from django.db import models
from django.db.models import Sum # Jami to'lovni hisoblash uchun
from django.conf import settings
from django.utils import timezone
from sales.models import Sale, Customer # Boshqa app modellari
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from datetime import timedelta


class InstallmentPlan(models.Model):
    class PlanStatus(models.TextChoices):  # O'zgarishsiz
        ACTIVE = 'Active', 'Faol'
        PAID = 'Paid', 'Yakunlangan'
        OVERDUE = 'Overdue', 'Kechikkan'
        CANCELLED = 'Cancelled', 'Bekor qilingan'

    sale = models.OneToOneField(Sale, on_delete=models.CASCADE, related_name='installmentplan',
                                verbose_name="Asosiy Sotuv")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='installment_plans',
                                 verbose_name="Mijoz")

    # YANGI: Nasiyaning asosiy valyutasi (Sotuv valyutasidan olinadi)
    currency = models.CharField(
        max_length=3,
        choices=Sale.SaleCurrency.choices,  # Sale modelidagi choices ni ishlatamiz
        verbose_name="Nasiya Valyutasi"
    )

    initial_amount = models.DecimalField(max_digits=17, decimal_places=2,
                                         verbose_name="Asosiy Qarz Summasi (nasiya valyutasida)")
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal(0),
                                        validators=[MinValueValidator(Decimal(0))],
                                        verbose_name="Foiz Stavka (%)")  # MaxValue olib tashlandi
    term_months = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Muddat (oylar)")
    down_payment = models.DecimalField(max_digits=17, decimal_places=2, default=Decimal(0),
                                       verbose_name="Boshlang'ich To'lov (nasiya valyutasida)")

    total_amount_due = models.DecimalField(max_digits=17, decimal_places=2, blank=True, null=True,
                                           verbose_name="Jami To'lanishi Kerak (nasiya valyutasida)")
    monthly_payment = models.DecimalField(max_digits=17, decimal_places=2, blank=True, null=True,
                                          verbose_name="Taxminiy Oylik To'lov (nasiya valyutasida)")
    amount_paid = models.DecimalField(max_digits=17, decimal_places=2, default=Decimal(0),
                                      verbose_name="Jami To'langan (nasiya valyutasida)")

    status = models.CharField(max_length=10, choices=PlanStatus.choices, default=PlanStatus.ACTIVE,
                              verbose_name="Holati")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Yaratilgan sana")
    return_adjustment = models.DecimalField(max_digits=17, decimal_places=2, default=Decimal(0),
                                            verbose_name="Qaytarish Tuzatishi (nasiya valyutasida)")

    class Meta:
        verbose_name = "Nasiya Rejasi"
        verbose_name_plural = "Nasiya Rejalari"
        ordering = ['-created_at']

    def __str__(self):
        return f"Nasiya #{self.id} ({self.customer.full_name}) - {self.total_amount_due} {self.currency}"

    @property
    def total_interest(self):
        if self.total_amount_due is not None and self.initial_amount is not None:
            return self.total_amount_due - self.initial_amount
        return Decimal(0)

    @property
    def remaining_amount(self):
        if self.total_amount_due is None:
            return self.initial_amount - (self.down_payment or Decimal(0))  # Agar total_due hisoblanmagan bo'lsa
        remaining = self.total_amount_due - (self.return_adjustment or Decimal(0)) - (self.amount_paid or Decimal(0))
        return max(remaining, Decimal(0))

    @property
    def get_next_payment_due_date(self):
        if not hasattr(self, '_cached_schedule'):  # Agar schedule prefetch qilingan bo'lsa
            self._cached_schedule = list(self.schedule.filter(is_paid=False).order_by('due_date'))

        next_payment = next((entry for entry in self._cached_schedule if not entry.is_paid), None)
        return next_payment.due_date if next_payment else None

    def is_overdue(self):
        next_due_date = self.get_next_payment_due_date
        return (
                self.status == self.PlanStatus.ACTIVE and
                next_due_date and
                next_due_date < timezone.now().date()
        )

    def update_status(self, force_save=False):
        if self.status == self.PlanStatus.CANCELLED: return

        # Barcha grafik yozuvlari to'langanligini schedule dan tekshirish
        # Agar grafik hali yaratilmagan bo'lsa, bu xato berishi mumkin.
        # Yoki qoldiq summasi orqali tekshirish
        if self.pk and self.schedule.exists():  # Faqat plan saqlangan va grafigi bor bo'lsa
            all_schedule_entries_paid = not self.schedule.filter(is_paid=False).exists()
            if all_schedule_entries_paid:
                self.status = self.PlanStatus.PAID
            elif self.is_overdue():
                self.status = self.PlanStatus.OVERDUE
            else:
                self.status = self.PlanStatus.ACTIVE
        elif self.remaining_amount is not None and self.remaining_amount <= Decimal(0):
            self.status = self.PlanStatus.PAID
        elif self.is_overdue():  # Bu get_next_payment_due_date ga tayanadi, u esa schedule ga
            self.status = self.PlanStatus.OVERDUE
        else:
            self.status = self.PlanStatus.ACTIVE

        if force_save: self.save(update_fields=['status'])

    def calculate_and_generate_schedule(self):
        """Oylik to'lovni hisoblaydi va to'lov grafigini yaratadi. Bu metod SAQLAMAYDI."""
        if not self.initial_amount or self.term_months is None or self.term_months <= 0 or self.interest_rate is None:
            print(f"WARNING: Plan {self.id or 'NEW'} - Cannot calculate schedule. Missing data.")
            # total_amount_due va monthly_payment ni None qilib qoldiramiz yoki default hisoblaymiz
            self.total_amount_due = self.initial_amount  # Foizsiz deb olamiz
            self.monthly_payment = (
                                               self.initial_amount - self.down_payment) / self.term_months if self.term_months > 0 else (
                        self.initial_amount - self.down_payment)
            return  # Grafik yaratmaymiz

        total_interest_amount = self.initial_amount * (self.interest_rate / Decimal(100))
        self.total_amount_due = self.initial_amount + total_interest_amount

        amount_to_pay_over_term = self.total_amount_due - self.down_payment
        if self.term_months > 0:
            self.monthly_payment = amount_to_pay_over_term / Decimal(self.term_months)
        else:
            self.monthly_payment = amount_to_pay_over_term

        # --- Grafikni Yaratish (lekin DBga yozmaymiz, serializer qiladi) ---
        # Eski grafikni o'chirish (agar plan allaqachon DB da bo'lsa)
        if self.pk:  # Faqat mavjud planlar uchun
            self.schedule.all().delete()

        schedule_entries_to_create = []
        current_due_date = (self.created_at or timezone.now()).date()
        remaining_for_schedule_calc = amount_to_pay_over_term

        # Birinchi to'lov sanasi (masalan, keyingi oyning shu kuni yoki 30 kun keyin)
        # Bu logikani aniqlashtirish kerak
        try:
            current_due_date = current_due_date.replace(
                day=min(current_due_date.day, 28))  # Oyning oxirgi kunlari muammosini oldini olish
            current_due_date = current_due_date + timedelta(days=32)  # Taxminan 1 oy keyin
            current_due_date = current_due_date.replace(day=min(current_due_date.day, 28))  # Yana to'g'rilash
        except ValueError:  # Agar sana noto'g'ri bo'lsa (masalan, 31 fevral)
            current_due_date = (self.created_at or timezone.now()).date() + timedelta(days=30)

        for i in range(self.term_months):
            payment_this_month = round(self.monthly_payment, 2)
            if i == self.term_months - 1:  # Oxirgi oy
                payment_this_month = remaining_for_schedule_calc  # Qolgan qoldiq

            if payment_this_month > Decimal('0.005'):  # Juda kichik summalarni e'tiborsiz qoldirish
                schedule_entries_to_create.append(PaymentSchedule(
                    plan=self,  # Bu yerda self hali DB da bo'lmasligi mumkin
                    due_date=current_due_date,
                    amount_due=payment_this_month
                ))
                remaining_for_schedule_calc -= payment_this_month

            # Keyingi sanani hisoblash
            try:
                next_month_day = current_due_date.day
                current_due_date = current_due_date + timedelta(days=32)  # Taxminan 1 oy
                current_due_date = current_due_date.replace(day=min(next_month_day, 28))
            except ValueError:
                current_due_date = current_due_date + timedelta(days=30)

        if i == self.term_months - 1 and remaining_for_schedule_calc > Decimal('0.01') and schedule_entries_to_create:
            schedule_entries_to_create[-1].amount_due += remaining_for_schedule_calc

    @property
    def total_paid(self):
        """To'langan jami summa"""
        return self.payments.aggregate(Sum('amount'))['amount__sum'] or Decimal(0)

    @property
    def total_profit(self):
        """Umumiy foyda (to'langan pul)"""
        return self.total_paid

    def update_profit(self):
        """To'langan pulni yangilash"""
        self.save(update_fields=['amount_paid'])


class PaymentSchedule(models.Model):
    """Nasiya rejasi uchun to'lovlar grafigi"""
    plan = models.ForeignKey(InstallmentPlan, related_name='schedule', on_delete=models.CASCADE, verbose_name="Nasiya Rejasi")
    due_date = models.DateField(verbose_name="To'lov Sanasi")
    amount_due = models.DecimalField(max_digits=17, decimal_places=2, verbose_name="To'lanishi Kerak Summa")
    amount_paid = models.DecimalField(max_digits=17, decimal_places=2, default=0, verbose_name="Haqiqatda To'langan") # Nomi o'zgardi
    is_paid = models.BooleanField(default=False, verbose_name="To'langan")
    payment_date = models.DateTimeField(null=True, blank=True, verbose_name="Haqiqiy To'lov Sanasi")

    class Meta:
        verbose_name = "To'lov Grafigi Yozuvi"
        verbose_name_plural = "To'lov Grafigi Yozuvlari"
        ordering = ['plan', 'due_date']
        unique_together = ('plan', 'due_date')

    def __str__(self):
        return f"Reja #{self.plan_id}: {self.due_date} - {self.amount_due} UZS {'(Tolangan)' if self.is_paid else ''}"

    @property
    def remaining_on_entry(self):
        """Shu grafik yozuvi uchun qolgan summa"""
        return max(self.amount_due - self.amount_paid, Decimal(0))


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
        return f"To'lov #{self.id} - {self.amount} UZS"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # To'lov saqlanganidan so'ng foyda hisoblanadi
        self.plan.update_profit()

    @property
    def profit(self):
        """To'langan summa foyda sifatida hisoblanadi"""
        return self.amount