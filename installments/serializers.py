# installments/serializers.py
import traceback
from datetime import date, timedelta

from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from .models import InstallmentPlan, InstallmentPayment, PaymentSchedule # PaymentSchedule qo'shildi
from sales.models import Sale, Customer
# Serializerlarni import qilish (circular importni oldini olish uchun kerak bo'lsa type hinting)
from sales.serializers import CustomerSerializer, SaleListSerializer
from users.serializers import UserSerializer

# --- Chiqish Uchun Serializerlar ---

class PaymentScheduleSerializer(serializers.ModelSerializer):
    """To'lov grafigini ko'rsatish uchun"""
    remaining_on_entry = serializers.ReadOnlyField()

    class Meta:
        model = PaymentSchedule
        fields = ['id', 'due_date', 'amount_due', 'amount_paid', 'remaining_on_entry', 'is_paid', 'payment_date']


class InstallmentPaymentSerializer(serializers.ModelSerializer):
    """Nasiya to'lovlarini ko'rsatish uchun"""
    received_by_username = serializers.CharField(source='received_by.username', read_only=True, default=None)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)

    class Meta:
        model = InstallmentPayment
        fields = ['id', 'amount', 'payment_date', 'payment_method', 'payment_method_display', 'received_by_username']


class InstallmentPlanListSerializer(serializers.ModelSerializer):
     """Nasiya rejalari ro'yxati uchun"""
     customer_name = serializers.CharField(source='customer.full_name', read_only=True)
     sale_id = serializers.IntegerField(source='sale.id', read_only=True)
     remaining_amount = serializers.ReadOnlyField() # Jami qoldiq (foiz bilan)
     status_display = serializers.CharField(source='get_status_display', read_only=True)
     next_payment_due_date = serializers.DateField(source='get_next_payment_due_date', read_only=True) # Grafikdan
     is_overdue = serializers.SerializerMethodField()

     class Meta:
         model = InstallmentPlan
         fields = [
             'id', 'sale_id', 'customer_name',
             'initial_amount', # Asl narx
             'interest_rate', # Foiz
             'term_months', # Muddat
             'monthly_payment', # Oylik to'lov (taxminiy)
             'total_amount_due', # Jami qarz
             'down_payment', # Boshlang'ich to'lov
             'amount_paid', # Jami to'langan
             'remaining_amount', # Qolgan qarz
             'next_payment_due_date', # Keyingi sana
             'status', 'status_display', 'is_overdue', 'created_at'
         ]

     def get_is_overdue(self, obj):
          return obj.is_overdue() # Model metodini chaqirish


class InstallmentPlanDetailSerializer(InstallmentPlanListSerializer):
     """Bitta nasiya rejasining batafsil ma'lumoti"""
     payments = InstallmentPaymentSerializer(many=True, read_only=True) # To'lovlar tarixi
     schedule = PaymentScheduleSerializer(many=True, read_only=True) # To'lov grafigi
     sale = SaleListSerializer(read_only=True)
     customer = CustomerSerializer(read_only=True)
     total_interest = serializers.ReadOnlyField() # Jami foiz summasi

     class Meta(InstallmentPlanListSerializer.Meta):
         fields = InstallmentPlanListSerializer.Meta.fields + [
             'payments', 'schedule', 'sale', 'customer', 'return_adjustment', 'total_interest'
         ]

# --- Kirish Uchun Serializerlar ---

class InstallmentPlanCreateSerializer(serializers.Serializer):
    """Yangi nasiya rejasi yaratish uchun (ichki)."""
    # Bu maydonlar SaleCreateSerializer dan keladi (obyekt ID lari sifatida)
    sale = serializers.PrimaryKeyRelatedField(queryset=Sale.objects.all())
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())

    # Bu maydonlar ham SaleCreateSerializer dan (installment_* prefiksi bilan) keladi
    initial_amount = serializers.DecimalField(
        max_digits=17, decimal_places=2, min_value=Decimal('0.01'),
        help_text="Mahsulotning asl narxi (foizsiz, UZS)"
    )
    down_payment = serializers.DecimalField(
        max_digits=17, decimal_places=2, default=Decimal(0), min_value=Decimal(0),
        help_text="Boshlang'ich to'lov (UZS)"
    )
    interest_rate = serializers.DecimalField(  # Yillik foiz stavkasi deb faraz qilamiz
        max_digits=5, decimal_places=2, default=Decimal(0), min_value=Decimal(0),
        help_text="Foiz stavkasi (masalan, yillik %)"
    )
    term_months = serializers.IntegerField(
        min_value=1,
        help_text="Nasiya muddati (oylar)"
    )

    def validate_initial_amount(self, value):
        if value <= Decimal(0):
            raise serializers.ValidationError("Mahsulot narxi 0 dan katta bo'lishi kerak.")
        return value

    def validate_term_months(self, value):
        if value <= 0:
            raise serializers.ValidationError("Nasiya muddati 0 dan katta bo'lishi kerak.")
        return value

    def validate(self, data):
        initial_amount = data.get('initial_amount')
        down_payment = data.get('down_payment', Decimal(0))
        term_months = data.get('term_months')

        if initial_amount is None or term_months is None:
            # Bu holat required=True tufayli bo'lmasligi kerak, lekin himoya uchun
            raise serializers.ValidationError("Asosiy summa va muddat kiritilishi shart.")

        if down_payment > initial_amount:
            raise serializers.ValidationError({
                "down_payment": "Boshlang'ich to'lov asosiy summadan katta bo'lishi mumkin emas."
            })

        # Agar boshlang'ich to'lov asosiy summaga teng yoki katta bo'lsa va muddat 1 dan katta bo'lsa, mantiqsiz
        if down_payment >= initial_amount and term_months > 0:
            # Bu nasiya emas, to'liq sotuv bo'lishi kerak edi.
            # Yoki term_months = 0 bo'lishi kerak (agar shunday logika bo'lsa)
            # Hozircha, agar down_payment = initial_amount bo'lsa, nasiya yaratamiz, lekin grafik bo'sh bo'ladi
            pass

        print(f"[DEBUG][InstallmentPlanCreateSerializer.validate] Validated data: {data}")
        return data

    @transaction.atomic
    def create(self, validated_data):
        print(f"[DEBUG][IPCSerializer.create] Starting with: {validated_data}")

        plan_data_for_create = validated_data.copy()
        # amount_paid boshlang'ich to'lovni o'z ichiga oladi
        plan_data_for_create['amount_paid'] = validated_data.get('down_payment', Decimal(0))

        # total_amount_due va monthly_payment hali hisoblanmagan
        plan_data_for_create.pop('total_amount_due', None)
        plan_data_for_create.pop('monthly_payment', None)

        plan = None
        try:
            plan = InstallmentPlan.objects.create(**plan_data_for_create)
            print(f"[DEBUG][IPCSerializer.create] Plan CREATED with ID: {plan.id if plan else 'None'}")
        except Exception as e_create:
            print(
                f"[DEBUG][IPCSerializer.create] !!! ERROR during InstallmentPlan.objects.create: {traceback.format_exc()}")
            raise serializers.ValidationError(f"Nasiya rejasini DBga yozishda xatolik: {e_create}")

        if not plan or not plan.pk:
            raise serializers.ValidationError("Nasiya rejasi obyekti DBda yaratilmadi.")

        try:
            print(f"[DEBUG][IPCSerializer.create] Calculating schedule for plan ID: {plan.id}")
            # 1. total_amount_due va monthly_payment ni hisoblash va plan obyektiga o'rnatish
            # Foizni umumiy muddat uchun deb hisoblaymiz (sodda foiz)
            total_interest_amount = plan.initial_amount * (plan.interest_rate / Decimal(100))
            plan.total_amount_due = plan.initial_amount + total_interest_amount

            amount_to_pay_via_schedule = plan.total_amount_due - plan.down_payment
            if plan.term_months > 0:
                plan.monthly_payment = (amount_to_pay_via_schedule / Decimal(plan.term_months)).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:  # Bu holat validatsiyada ushlanishi kerak (term_months >= 1)
                plan.monthly_payment = amount_to_pay_via_schedule  # Yoki 0?

            print(
                f"[DEBUG][IPCSerializer.create] Calculated: total_due={plan.total_amount_due}, monthly={plan.monthly_payment}")
            plan.save(update_fields=['total_amount_due', 'monthly_payment'])
            print(f"[DEBUG][IPCSerializer.create] Saved total_due and monthly_payment for plan ID: {plan.id}")

            # 2. To'lov Grafigini Yaratish
            schedule_entries_to_create = []
            # Birinchi to'lov sanasini plan yaratilgan kundan bir oy keyingi sana qilib olamiz
            # Masalan, agar 15-mayda yaratilsa, birinchi to'lov 15-iyun.
            current_payment_date = plan.created_at.date()

            total_scheduled_amount = Decimal(0)

            for i in range(plan.term_months):
                # Keyingi oyni topish
                month_to_add = i + 1
                next_due_year = current_payment_date.year
                next_due_month = current_payment_date.month + month_to_add

                while next_due_month > 12:
                    next_due_month -= 12
                    next_due_year += 1

                # Oyning kunini boshlang'ich sanadagi kundan olishga harakat qilamiz,
                # lekin u kundan oshmasligini ta'minlaymiz (masalan, 31-kun)
                day_for_schedule = current_payment_date.day
                try:
                    due_date_obj = date(next_due_year, next_due_month, day_for_schedule)
                except ValueError:  # Agar kun xato bo'lsa (masalan, 31 fevral)
                    # Oyning oxirgi kunini olamiz
                    if next_due_month == 12:
                        due_date_obj = date(next_due_year, next_due_month, 31)
                    else:
                        due_date_obj = date(next_due_year, next_due_month + 1, 1) - timedelta(days=1)

                payment_this_month = plan.monthly_payment  # Odatdagi oylik to'lov

                # Oxirgi to'lovni qoldiqqa moslashtirish
                if i == plan.term_months - 1:
                    payment_this_month = amount_to_pay_via_schedule - total_scheduled_amount

                payment_this_month = payment_this_month.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                if payment_this_month > Decimal(0):  # Faqat 0 dan katta bo'lsa qo'shamiz
                    schedule_entries_to_create.append(PaymentSchedule(
                        plan=plan,
                        due_date=due_date_obj,
                        amount_due=payment_this_month
                    ))
                    total_scheduled_amount += payment_this_month

            if schedule_entries_to_create:
                PaymentSchedule.objects.bulk_create(schedule_entries_to_create)
                print(
                    f"[DEBUG][IPCSerializer.create] Created {len(schedule_entries_to_create)} schedule entries for plan ID: {plan.id}")
            else:
                print(f"[DEBUG][IPCSerializer.create] No schedule entries to create for plan ID: {plan.id}")

            # Statusni yangilash
            plan.update_status(force_save=True)
            print(f"[DEBUG][IPCSerializer.create] Plan status updated for ID: {plan.id}. Status: {plan.status}")

        except Exception as e_schedule:
            print(
                f"[DEBUG][IPCSerializer.create] !!! ERROR during schedule/status for plan ID: {plan.id if plan else 'None'}:")
            print(traceback.format_exc())
            # Tranzaksiya orqaga qaytadi, qo'shimcha tozalash shart emas
            raise serializers.ValidationError(f"Nasiya grafigini yaratish/hisoblashda xatolik: {e_schedule}")

        print(f"[DEBUG][IPCSerializer.create] FINISHED. Returning plan object ID: {plan.id}")
        return plan  # Model obyektini qaytarish


class InstallmentPaySerializer(serializers.Serializer):
    """Nasiyaga to'lov qilish uchun"""
    amount = serializers.DecimalField(max_digits=17, decimal_places=2, min_value=Decimal('0.01'), label="To'lov summasi")
    payment_method = serializers.ChoiceField(choices=InstallmentPayment.PaymentMethod.choices, label="To'lov usuli")

    def validate_amount(self, value):
         # To'lov qoldiqdan oshmasligini tekshirish (ixtiyoriy, lekin foydali)
         plan = self.context.get('plan') # Viewdan keladi
         if plan and value > plan.remaining_amount:
              # Xatolik berish yoki miqdorni chegaralash
              # raise serializers.ValidationError(f"To'lov miqdori qoldiqdan ({plan.remaining_amount:.2f} UZS) oshmasligi kerak.")
              print(f"Payment amount {value} exceeds remaining {plan.remaining_amount}. Adjusting...")
              return plan.remaining_amount # Faqat qoldiqni qaytarish
         return value

    def save(self, **kwargs):
        plan = kwargs['plan']
        user = kwargs['user']
        amount_received = self.validated_data['amount'] # Qancha pul keldi
        payment_method = self.validated_data['payment_method']

        # Qoldiqni tekshirish (agar validate_amount da chegaralanmagan bo'lsa)
        amount_to_pay = min(amount_received, plan.remaining_amount)

        if amount_to_pay <= 0:
             raise serializers.ValidationError({"amount": "To'lov miqdori 0 dan katta bo'lishi kerak yoki qarz yo'q."})

        with transaction.atomic():
            # To'lov yozuvini yaratish
            # Bu o'z navbatida plan.save() ni chaqiradi va grafik/statusni yangilaydi
            payment = InstallmentPayment.objects.create(
                plan=plan,
                amount=amount_to_pay, # Faqat kerakli miqdorni saqlaymiz
                payment_method=payment_method,
                received_by=user,
                payment_date=timezone.now()
            )

            # Kassa tranzaksiyasini yaratish (agar Naqd/Karta bo'lsa)
            # Bu kodni InstallmentPayment.save() ichiga ko'chirish ham mumkin
            from sales.models import KassaTransaction
            payment_method_enum = InstallmentPayment.PaymentMethod
            if payment_method in [payment_method_enum.CASH, payment_method_enum.CARD]:
                 KassaTransaction.objects.create(
                     kassa=plan.sale.kassa, amount=amount_to_pay,
                     transaction_type=KassaTransaction.TransactionType.INSTALLMENT_PAYMENT,
                     user=user, comment=f"Nasiya #{plan.id} uchun to'lov",
                     related_installment_payment=payment
                 )

        # Yaratilgan to'lov obyektini serializer orqali qaytarish
        return InstallmentPaymentSerializer(payment).data