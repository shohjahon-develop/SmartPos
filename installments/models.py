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
    """
    Nasiya shartnomasi (foizli va grafikli)
    """
    class PlanStatus(models.TextChoices):
        ACTIVE = 'Active', 'Faol'
        PAID = 'Paid', 'Yakunlangan'
        OVERDUE = 'Overdue', 'Kechikkan'
        CANCELLED = 'Cancelled', 'Bekor qilingan' # Sotuv qaytarilganda

    sale = models.OneToOneField(
        Sale,
        on_delete=models.CASCADE, # Sotuv o'chsa, nasiya ham o'chadi
        related_name='installmentplan',
        verbose_name="Asosiy Sotuv"
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT, # Mijoz o'chsa nasiya qolishi kerak
        related_name='installment_plans',
        verbose_name="Mijoz"
    )

    # Nasiya Shartlari
    initial_amount = models.DecimalField(
        max_digits=17, decimal_places=2,
        verbose_name="Mahsulot Narxi (UZS)",
        help_text="Nasiya olingandagi asl narx (foizsiz)"
    )
    interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal(0)), MaxValueValidator(Decimal(100))],
        verbose_name="Foiz Stavka (%)",
        help_text="Nasiya uchun qo'shiladigan umumiy foiz (butun muddat uchun)"
    )
    term_months = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Muddat (oylar)"
    )
    down_payment = models.DecimalField(
        max_digits=17, decimal_places=2, default=0,
        verbose_name="Boshlang'ich To'lov (UZS)"
    )

    # Hisoblangan Qiymatlar
    total_amount_due = models.DecimalField(
        max_digits=17, decimal_places=2, blank=True, # Avtomatik hisoblanadi
        verbose_name="Jami To'lanishi Kerak (Foiz Bilan, UZS)"
    )
    monthly_payment = models.DecimalField(
        max_digits=17, decimal_places=2, blank=True, null=True, # Avtomatik hisoblanadi
        verbose_name="Taxminiy Oylik To'lov (UZS)"
    )
    amount_paid = models.DecimalField(
        max_digits=17, decimal_places=2, default=0,
        verbose_name="Jami To'langan (UZS)",
        help_text="Boshlang'ich to'lovni ham o'z ichiga oladi"
    )

    # Holat va Boshqa Ma'lumotlar
    status = models.CharField(
        max_length=10, choices=PlanStatus.choices, default=PlanStatus.ACTIVE, verbose_name="Holati"
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Yaratilgan sana")
    # Sotuv qaytarilganda o'zgarishi mumkin
    return_adjustment = models.DecimalField(
        max_digits=17, decimal_places=2, default=0, verbose_name="Qaytarish Tuzatishi (UZS)"
    )

    class Meta:
        verbose_name = "Nasiya Rejasi"
        verbose_name_plural = "Nasiya Rejalari"
        ordering = ['-created_at']

    def __str__(self):
        return f"Nasiya #{self.id} ({self.customer.full_name}) - {self.term_months} oy / {self.interest_rate}%"

    @property
    def total_interest(self):
        """Jami hisoblangan foiz summasi"""
        if self.total_amount_due and self.initial_amount:
             return self.total_amount_due - self.initial_amount
        return Decimal(0)

    @property
    def remaining_amount(self):
        """Qolgan jami qarz (foiz bilan)"""
        if self.total_amount_due is None: # Agar hali hisoblanmagan bo'lsa
            return None
        remaining = self.total_amount_due - (self.return_adjustment or 0) - (self.amount_paid or 0)
        return max(remaining, Decimal(0))

    @property
    def get_next_payment_due_date(self):
        """Grafikdan keyingi to'lanmagan to'lov sanasini olish"""
        # schedule related_name orqali PaymentSchedule ga bog'lanadi
        next_payment = self.schedule.filter(is_paid=False).order_by('due_date').first()
        return next_payment.due_date if next_payment else None

    def is_overdue(self):
        """Muddati o'tgan to'lov borligini tekshirish"""
        next_due_date = self.get_next_payment_due_date
        return (
            self.status == self.PlanStatus.ACTIVE and
            next_due_date and
            next_due_date < timezone.now().date()
        )

    def update_status(self, force_save=False):
        """Nasiya holatini avtomatik yangilaydi"""
        if self.status == self.PlanStatus.CANCELLED: return

        # Barcha grafik to'lovlari to'langanligini tekshirish
        all_paid = not self.schedule.filter(is_paid=False).exists()
        # Yoki qoldiq summasi orqali tekshirish
        # remaining = self.remaining_amount

        if all_paid: # Yoki (remaining is not None and remaining <= 0):
             self.status = self.PlanStatus.PAID
        elif self.is_overdue():
             self.status = self.PlanStatus.OVERDUE
        else:
             self.status = self.PlanStatus.ACTIVE

        if force_save: self.save(update_fields=['status'])

    def calculate_and_generate_schedule(self):
        """Oylik to'lovni hisoblaydi va to'lov grafigini yaratadi."""
        if not self.initial_amount or not self.term_months or self.interest_rate is None:
            # Kerakli ma'lumotlar yo'q bo'lsa, hisoblash mumkin emas
             print(f"WARNING: Cannot calculate schedule for Plan {self.id}. Missing data.")
             self.total_amount_due = self.initial_amount # Foizsiz deb hisoblash
             self.monthly_payment = (self.initial_amount - self.down_payment) / self.term_months if self.term_months > 0 else self.initial_amount - self.down_payment
             # Grafik yaratmaslik yoki bo'sh grafik yaratish mumkin
             return # Grafik yaratmaymiz

        # --- Foiz va Jami Summani Hisoblash (Sodda usul) ---
        # Foiz = Asosiy * (Stavka/100) (Umumiy foiz deb hisoblaymiz)
        # Moliyaviy aniq hisoblash uchun annuitet formulasi kerak bo'lishi mumkin
        total_interest = self.initial_amount * (self.interest_rate / Decimal(100))
        self.total_amount_due = self.initial_amount + total_interest

        # --- Oylik To'lovni Hisoblash ---
        amount_to_pay_over_term = self.total_amount_due - self.down_payment
        if self.term_months > 0:
            # Oxirgi to'lovda qoldiqni to'g'rilash uchun round() o'rniga floor/ceil ishlatish kerak bo'lishi mumkin
            # yoki oxirgi to'lovni alohida hisoblash
            self.monthly_payment = amount_to_pay_over_term / self.term_months
        else:
             self.monthly_payment = amount_to_pay_over_term # Muddat 0 bo'lsa

        # total_amount_due va monthly_payment ni saqlash
        self.save(update_fields=['total_amount_due', 'monthly_payment'])

        # --- Grafikni Yaratish ---
        self.schedule.all().delete() # Eski grafikni o'chirish

        schedule_entries = []
        # Grafik boshlanish sanasi (masalan, yaratilganidan 1 oy keyin)
        # Yoki frontenddan kelishi kerak? Hozircha 1 oy keyin deb olamiz
        first_due_date = (self.created_at or timezone.now()).date() + timedelta(days=30) # Taxminiy
        current_due_date = first_due_date
        remaining_for_schedule = amount_to_pay_over_term

        for i in range(self.term_months):
            # Har oyning keyingi sanasiga o'tish logikasi (murakkab bo'lishi mumkin)
            # Sodda variant: har oyga ~30.4 kun qo'shish yoki har oyning ma'lum bir sanasi
            # Keling, har oyga 1 oy qo'shamiz (taxminiy)
            if i > 0:
                 # Keyingi oyning shu kuniga o'tishga harakat qilamiz
                 try:
                     # Agar fevral 30/31 bo'lmasa, xato beradi
                     next_month_day = current_due_date.day
                     next_month = current_due_date.month + 1
                     next_year = current_due_date.year
                     if next_month > 12:
                          next_month = 1
                          next_year += 1
                     #replace() ishlatish xavfli kun yo'q bo'lsa
                     # current_due_date = current_due_date.replace(year=next_year, month=next_month, day=next_month_day)
                     # Oddiyroq yondashuv: taxminan 30 kun qo'shish
                     current_due_date = current_due_date + timedelta(days=30) # Juda sodda!
                 except ValueError:
                     # Oyning oxirgi kuniga to'g'rilash kerak
                     current_due_date = current_due_date + timedelta(days=30) # Hozircha sodda


            # Oylik to'lov miqdori (oxirgi to'lovni to'g'rilash)
            # Rounding xatolarini oldini olish uchun to'g'ri hisoblash muhim
            payment_this_month = round(self.monthly_payment, 2) # Har doim 2 xona aniqlikda
            if i == self.term_months - 1: # Oxirgi oy
                 payment_this_month = remaining_for_schedule # Qolgan qoldiqni to'liq olish

            # Miqdor 0 dan katta bo'lsa qo'shamiz
            if payment_this_month > 0:
                schedule_entries.append(PaymentSchedule(
                    plan=self,
                    due_date=current_due_date,
                    amount_due=payment_this_month
                ))
                remaining_for_schedule -= payment_this_month # Qoldiqni kamaytirish

            # Agar oxirgi to'lovdan keyin ham qoldiq qolsa (rounding xatosi tufayli)
            if i == self.term_months - 1 and remaining_for_schedule > Decimal('0.01'):
                print(f"WARNING: Small remaining balance {remaining_for_schedule} after final payment for plan {self.id}. Adjusting last payment.")
                schedule_entries[-1].amount_due += remaining_for_schedule
                remaining_for_schedule = Decimal(0)

        if schedule_entries:
             PaymentSchedule.objects.bulk_create(schedule_entries)
             print(f"Generated {len(schedule_entries)} schedule entries for plan {self.id}")
        else:
             print(f"WARNING: No schedule entries generated for plan {self.id}")


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
        return f"Reja #{self.plan_id}: {self.due_date} - {self.amount_due} UZS {"(To\'langan)" if self.is_paid else ''}"

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
    # Qaysi grafik yozuviga tegishli ekanligini saqlash mumkin (agar kerak bo'lsa)
    # comment = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Nasiya To'lovi"
        verbose_name_plural = "Nasiya To'lovlari"
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.amount} UZS to'lov (Reja #{self.plan_id}) - {self.payment_date.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
         is_new = self.pk is None
         super().save(*args, **kwargs)
         if is_new and self.amount > 0: # Faqat yangi va summasi bor to'lovlar uchun
              self.distribute_payment_to_schedule()

    def distribute_payment_to_schedule(self):
         """To'lovni grafik yozuvlari bo'yicha taqsimlaydi va plan statusini yangilaydi"""
         plan = self.plan
         payment_amount_to_distribute = self.amount
         print(f"Distributing payment of {payment_amount_to_distribute} for Plan {plan.id}")

         # To'lanmagan, muddati bo'yicha tartiblangan grafik yozuvlari
         due_entries = plan.schedule.filter(is_paid=False).order_by('due_date')

         for entry in due_entries:
              if payment_amount_to_distribute <= Decimal('0.01'): break # Taqsimlanadigan summa qolmadi

              needed = entry.remaining_on_entry # Qancha kerak
              pay_for_this_entry = min(payment_amount_to_distribute, needed)

              entry.amount_paid += pay_for_this_entry
              payment_amount_to_distribute -= pay_for_this_entry

              if entry.remaining_on_entry <= Decimal('0.01'): # Kichik qoldiqlarni hisobga olish
                  entry.is_paid = True
                  entry.payment_date = self.payment_date # Shu to'lov sanasi bilan yopildi
                  entry.amount_paid = entry.amount_due # Qoldiqni 0 qilish uchun

              entry.save(update_fields=['amount_paid', 'is_paid', 'payment_date'])
              print(f"  Paid {pay_for_this_entry} for entry {entry.id} (Due: {entry.due_date}). Remaining on entry: {entry.remaining_on_entry}")

         # Plan ning umumiy amount_paid ni qayta hisoblash (barcha to'lovlar yig'indisi)
         total_paid_on_plan = plan.payments.aggregate(total=Sum('amount', default=Decimal(0)))['total']
         plan.amount_paid = total_paid_on_plan
         plan.update_status() # Statusni yangilash
         plan.save(update_fields=['amount_paid', 'status'])
         print(f"Plan {plan.id} updated: amount_paid={plan.amount_paid}, status={plan.status}")