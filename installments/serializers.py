# installments/serializers.py
from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from .models import InstallmentPlan, InstallmentPayment
from sales.models import Sale, Customer # Queryset uchun
from sales.serializers import CustomerSerializer, SaleListSerializer # Bog'liq ma'lumotlar
from users.serializers import UserSerializer

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
     remaining_amount = serializers.ReadOnlyField()
     status_display = serializers.CharField(source='get_status_display', read_only=True)
     is_overdue = serializers.ReadOnlyField() # Model property

     class Meta:
         model = InstallmentPlan
         fields = [
             'id', 'sale_id', 'customer_name', 'total_due', 'amount_paid', 'remaining_amount',
             'next_payment_date', 'status', 'status_display', 'is_overdue', 'created_at'
         ]

class InstallmentPlanDetailSerializer(InstallmentPlanListSerializer):
     """Bitta nasiya rejasining batafsil ma'lumoti"""
     # Barcha to'lovlar ro'yxatini qo'shish
     payments = InstallmentPaymentSerializer(many=True, read_only=True)
     # Asosiy sotuv va mijoz haqida ko'proq ma'lumot
     sale = SaleListSerializer(read_only=True)
     customer = CustomerSerializer(read_only=True)

     class Meta(InstallmentPlanListSerializer.Meta):
         fields = InstallmentPlanListSerializer.Meta.fields + ['payments', 'sale', 'customer', 'return_adjustment']


class InstallmentPlanCreateSerializer(serializers.ModelSerializer):
     """Yangi nasiya rejasi yaratish uchun (ichki ishlatiladi)"""
     sale = serializers.PrimaryKeyRelatedField(queryset=Sale.objects.all())
     customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
     # next_payment_date ixtiyoriy, default qiymat berish mumkin (masalan, 1 oy keyin)
     next_payment_date = serializers.DateField(required=False, allow_null=True)

     class Meta:
         model = InstallmentPlan
         fields = ['sale', 'customer', 'total_due', 'amount_paid', 'next_payment_date']

     def validate(self, data):
         # Boshlang'ich to'lov umumiy summadan oshmasligi kerak
         if data.get('amount_paid', 0) > data['total_due']:
             raise serializers.ValidationError({"amount_paid": "Boshlang'ich to'lov umumiy summadan oshmasligi kerak."})
         # Agar next_payment_date berilmasa, default qiymat belgilash
         if not data.get('next_payment_date'):
              data['next_payment_date'] = timezone.now().date() + timezone.timedelta(days=30) # Masalan
         return data

     def create(self, validated_data):
         # amount_paid va total_due kelishini ta'minlash kerak
         plan = InstallmentPlan.objects.create(**validated_data)
         plan.update_status() # Statusni birinchi marta hisoblash
         return plan


class InstallmentPaySerializer(serializers.Serializer):
    """Nasiyaga to'lov qilish uchun"""
    amount = serializers.DecimalField(max_digits=17, decimal_places=2, min_value=0.01, label="To'lov summasi")
    payment_method = serializers.ChoiceField(choices=InstallmentPayment.PaymentMethod.choices, label="To'lov usuli")

    def validate_amount(self, value):
         # To'lov qoldiqdan oshmasligi kerakligini tekshirish (ixtiyoriy)
         # plan = self.context['plan'] # Viewdan keladi
         # if value > plan.remaining_amount:
         #     raise serializers.ValidationError(f"To'lov miqdori qoldiqdan ({plan.remaining_amount:.2f} UZS) oshmasligi kerak.")
         return value

    def save(self, **kwargs):
        plan = kwargs['plan']
        user = kwargs['user']
        amount = self.validated_data['amount']
        payment_method = self.validated_data['payment_method']

        # To'lov miqdori qoldiqdan oshib ketsa, faqat qoldiqni to'lash
        amount_to_pay = min(amount, plan.remaining_amount)
        if amount_to_pay <= 0:
             raise serializers.ValidationError({"amount": "To'lov miqdori 0 dan katta bo'lishi kerak yoki qarz yo'q."})

        with transaction.atomic():
            # To'lov yozuvini yaratish
            payment = InstallmentPayment.objects.create(
                plan=plan,
                amount=amount_to_pay, # Faqat qoldiq miqdoricha
                payment_method=payment_method,
                received_by=user,
                payment_date=timezone.now()
            )

            # Plan ning to'langan summasini yangilash
            plan.amount_paid += amount_to_pay
            # Keyingi to'lov sanasini yangilash (agar grafik bo'lsa murakkablashadi)
            # Hozirgi sodda variantda o'zgartirmaymiz yoki admin qo'lda o'zgartiradi
            # plan.next_payment_date = ...
            plan.update_status() # Statusni yangilash
            plan.save(update_fields=['amount_paid', 'status', 'next_payment_date'])
            from sales.models import KassaTransaction  # Funksiya ichida import qilish

            payment_method_enum = InstallmentPayment.PaymentMethod  # Enum ni olish
            if payment_method in [payment_method_enum.CASH, payment_method_enum.CARD]:
                # Karta uchun ham tranzaksiya yozamizmi? Hozircha ha.
                KassaTransaction.objects.create(
                    store=plan.store,  # Store ni Plandan olamiz
                    kassa=plan.sale.kassa,  # Kassani Plan ga bog'liq Sotuvdan olamiz
                    amount=amount_to_pay,
                    transaction_type=KassaTransaction.TransactionType.INSTALLMENT_PAYMENT,
                    user=user,
                    comment=f"Nasiya #{plan.id} uchun to'lov",
                    related_installment_payment=payment  # Yaratilgan to'lov obyekti
                )

        return InstallmentPaymentSerializer(payment).data # Yaratilgan to'lovni qaytarish