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


class PaymentScheduleSerializer(serializers.ModelSerializer):
    remaining_on_entry = serializers.ReadOnlyField()

    class Meta:
        model = PaymentSchedule
        fields = ['id', 'due_date', 'amount_due', 'amount_paid', 'remaining_on_entry', 'is_paid', 'payment_date']


class InstallmentPaymentSerializer(serializers.ModelSerializer):
    received_by_username = serializers.CharField(source='received_by.username', read_only=True, allow_null=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)

    # currency ni qo'shish mumkin (agar plan valyutasini ko'rsatish kerak bo'lsa)
    # currency = serializers.CharField(source='plan.currency', read_only=True)
    class Meta:
        model = InstallmentPayment
        fields = ['id', 'amount', 'payment_date', 'payment_method', 'payment_method_display',
                  'received_by_username']  # 'currency'


class InstallmentPlanListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    sale_id = serializers.IntegerField(source='sale.id', read_only=True)
    remaining_amount = serializers.ReadOnlyField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    next_payment_due_date = serializers.DateField(source='get_next_payment_due_date', read_only=True, allow_null=True)
    is_overdue = serializers.SerializerMethodField()
    currency = serializers.CharField(read_only=True)  # YANGI

    class Meta:
        model = InstallmentPlan
        fields = [
            'id', 'sale_id', 'customer_name', 'currency',  # currency qo'shildi
            'initial_amount', 'interest_rate', 'term_months', 'monthly_payment',
            'total_amount_due', 'down_payment', 'amount_paid', 'remaining_amount',
            'next_payment_due_date', 'status', 'status_display', 'is_overdue', 'created_at'
        ]

    def get_is_overdue(self, obj): return obj.is_overdue()


class InstallmentPlanDetailSerializer(InstallmentPlanListSerializer):
    payments = InstallmentPaymentSerializer(many=True, read_only=True)
    schedule = PaymentScheduleSerializer(many=True, read_only=True)
    # sale va customer uchun string yoki ID qaytaramiz (circular import oldini olish)
    sale = serializers.PrimaryKeyRelatedField(read_only=True)
    customer = serializers.PrimaryKeyRelatedField(read_only=True)
    total_interest = serializers.ReadOnlyField()

    class Meta(InstallmentPlanListSerializer.Meta):
        fields = InstallmentPlanListSerializer.Meta.fields + [
            'payments', 'schedule', 'sale', 'customer', 'return_adjustment', 'total_interest'
        ]


class InstallmentPlanCreateSerializer(serializers.Serializer):
    sale = serializers.PrimaryKeyRelatedField(queryset=Sale.objects.all())
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    currency = serializers.ChoiceField(choices=Sale.SaleCurrency.choices)  # Sotuvdan keladi
    initial_amount = serializers.DecimalField(max_digits=17, decimal_places=2, min_value=Decimal('0.01'))
    down_payment = serializers.DecimalField(max_digits=17, decimal_places=2, default=Decimal(0), min_value=Decimal(0))
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=Decimal(0), min_value=Decimal(0))
    term_months = serializers.IntegerField(min_value=1)

    def validate(self, data):
        if data.get('down_payment', Decimal(0)) > data.get('initial_amount', Decimal(0)):
            raise serializers.ValidationError(
                {"down_payment": "Boshlang'ich to'lov asosiy summadan katta bo'lishi mumkin emas."})
        return data

    @transaction.atomic
    def create(self, validated_data):
        plan_data = validated_data.copy()
        plan_data['amount_paid'] = plan_data.get('down_payment', Decimal(0))

        plan = InstallmentPlan.objects.create(**plan_data)

        # total_amount_due va monthly_payment ni hisoblash
        total_interest_val = plan.initial_amount * (plan.interest_rate / Decimal(100))
        plan.total_amount_due = plan.initial_amount + total_interest_val
        amount_to_pay_via_schedule = plan.total_amount_due - plan.down_payment
        if plan.term_months > 0:
            plan.monthly_payment = (amount_to_pay_via_schedule / Decimal(plan.term_months)).quantize(Decimal('0.01'),
                                                                                                     rounding=ROUND_HALF_UP)
        else:
            plan.monthly_payment = amount_to_pay_via_schedule
        plan.save(update_fields=['total_amount_due', 'monthly_payment'])

        # Grafikni yaratish
        schedule_entries = []
        # ... (avvalgi javobdagi grafik yaratish logikasi, `plan` obyektidan foydalanib) ...
        base_date = plan.created_at.date()
        total_scheduled = Decimal(0)
        for i in range(plan.term_months):
            month_offset = i + 1
            next_year, next_month = base_date.year, base_date.month + month_offset
            while next_month > 12: next_month -= 12; next_year += 1
            day = min(base_date.day, 28)  # Sodda yondashuv
            try:
                due_date = date(next_year, next_month, day)
            except ValueError:  # Agar kun xato bo'lsa (masalan, 31 fevral)
                due_date = date(next_year, next_month + 1, 1) - timedelta(days=1) if next_month < 12 else date(
                    next_year, next_month, 31)

            current_payment_amount = plan.monthly_payment
            if i == plan.term_months - 1:  # Oxirgi to'lov
                current_payment_amount = amount_to_pay_via_schedule - total_scheduled

            current_payment_amount = current_payment_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if current_payment_amount > Decimal(0):
                schedule_entries.append(
                    PaymentSchedule(plan=plan, due_date=due_date, amount_due=current_payment_amount))
                total_scheduled += current_payment_amount

        if schedule_entries: PaymentSchedule.objects.bulk_create(schedule_entries)

        plan.update_status(force_save=True)
        return plan


class InstallmentPaySerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=17, decimal_places=2, min_value=Decimal('0.01'))
    payment_method = serializers.ChoiceField(choices=InstallmentPayment.PaymentMethod.choices)

    # Bu serializerda currency kerak emas, chunki to'lov plan valyutasida bo'ladi

    def validate_amount(self, value):
        plan = self.context.get('plan')
        if plan and value > plan.remaining_amount:
            return plan.remaining_amount  # Faqat qoldiqni qaytarish
        return value

    def save(self, **kwargs):
        plan = kwargs['plan']
        user = kwargs['user']
        amount_received = self.validated_data['amount']
        payment_method = self.validated_data['payment_method']
        amount_to_pay = min(amount_received, plan.remaining_amount)

        if amount_to_pay <= 0:
            raise serializers.ValidationError({"amount": "To'lov miqdori 0 dan katta bo'lishi kerak yoki qarz yo'q."})

        with transaction.atomic():
            payment = InstallmentPayment.objects.create(
                plan=plan, amount=amount_to_pay, payment_method=payment_method,
                received_by=user, payment_date=timezone.now()
            )
            # KassaTransaction (agar UZS bo'lsa)
            if plan.currency == Sale.SaleCurrency.UZS and payment_method in [InstallmentPayment.PaymentMethod.CASH,
                                                                             InstallmentPayment.PaymentMethod.CARD]:
                from sales.models import KassaTransaction  # Faqat shu yerda import
                KassaTransaction.objects.create(
                    kassa=plan.sale.kassa, amount=amount_to_pay,
                    transaction_type=KassaTransaction.TransactionType.INSTALLMENT_PAYMENT,
                    user=user, comment=f"Nasiya #{plan.id} uchun to'lov",
                    related_installment_payment=payment
                )
        return InstallmentPaymentSerializer(payment).data