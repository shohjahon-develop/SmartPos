# installments/serializers.py
from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
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
    """Yangi nasiya rejasi yaratish uchun (ichki)"""
    sale = serializers.PrimaryKeyRelatedField(queryset=Sale.objects.all())
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    initial_amount = serializers.DecimalField(max_digits=17, decimal_places=2, min_value=Decimal('0.01'))
    down_payment = serializers.DecimalField(max_digits=17, decimal_places=2, default=Decimal(0), min_value=Decimal(0))
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=Decimal(0), min_value=Decimal(0))
    term_months = serializers.IntegerField(min_value=1)

    def validate(self, data):
        if data['down_payment'] > data['initial_amount']:
             raise serializers.ValidationError({"down_payment": "Boshlang'ich to'lov asosiy summadan katta bo'lishi mumkin emas."})
        return data

    def create(self, validated_data):
        # Boshlang'ich to'lovni amount_paid ga ham yozamiz
        validated_data['amount_paid'] = validated_data['down_payment']

        # Plan obyektini yaratish
        plan = InstallmentPlan.objects.create(**validated_data)

        # Oylik to'lovni hisoblash va grafikni generatsiya qilish
        try:
            plan.calculate_and_generate_schedule()
            # Statusni hisoblash (odatda 'Active' bo'ladi)
            plan.update_status(force_save=True) # Statusni ham saqlash
        except Exception as e:
             # Agar hisoblashda xato bo'lsa, tranzaksiya (agar mavjud bo'lsa) orqaga qaytadi
             print(f"Error creating schedule for new plan {plan.id}: {e}")
             # Bu xatoni yuqoriga uzatish kerak (raise)
             raise serializers.ValidationError(f"Nasiya grafigini hisoblashda/yaratishda xatolik: {e}")

        return plan


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