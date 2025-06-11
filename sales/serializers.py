# # sales/serializers.py
# from decimal import Decimal
#
# from rest_framework import serializers
# from django.db import transaction
# from rest_framework.exceptions import PermissionDenied, ValidationError
# from rest_framework.validators import UniqueValidator # <<<--- SHU QATORNI QO'SHING
# from installments.models import InstallmentPlan
# # SaleStatus ni bu importdan olib tashlaymiz:
# from .models import Customer, Sale, SaleItem, KassaTransaction
# from .models import Customer, Sale, SaleItem, SaleReturn, SaleReturnItem
# from products.models import Product, Kassa
# from products.serializers import ProductSerializer as ProductListSerializer, ProductSerializer
# from products.serializers import KassaSerializer
# from users.serializers import UserSerializer
# from inventory.models import ProductStock, InventoryOperation
# from django.utils import timezone
# from rest_framework.validators import UniqueValidator
# # Installments importlarini fayl boshidan olib tashlaymiz
# # from installments.serializers import InstallmentPlanCreateSerializer # <<< Olib tashlandi
# # from installments.models import InstallmentPlan                   # <<< Olib tashlandi
#
# class CustomerSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Customer
#         fields = ['id', 'full_name', 'phone_number', 'email', 'address', 'created_at']
#         read_only_fields = ('created_at',)
#         extra_kwargs = {
#             'phone_number': {
#                 'validators': [
#                     UniqueValidator( # Endi bu to'g'ri ishlaydi
#                         queryset=Customer.objects.all(),
#                         message="Bu telefon raqami bilan mijoz allaqachon mavjud."
#                     )
#                 ]
#             }
#         }
#
#
# class SaleItemSerializer(serializers.ModelSerializer):
#     product = ProductSerializer(read_only=True)
#     item_total_in_sale_currency = serializers.DecimalField(max_digits=17, decimal_places=2, read_only=True)
#
#     class Meta:
#         model = SaleItem
#         fields = [
#             'id', 'product', 'quantity',
#             'price_at_sale_usd', 'price_at_sale_uzs',
#             'item_total_in_sale_currency',
#             'quantity_returned', 'quantity_available_to_return'
#         ]
#
#
# class SaleListSerializer(serializers.ModelSerializer):
#     seller_username = serializers.CharField(source='seller.username', read_only=True, allow_null=True)
#     customer_name = serializers.CharField(source='customer.full_name', read_only=True, allow_null=True)
#     kassa_name = serializers.CharField(source='kassa.name', read_only=True)
#     payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
#     status_display = serializers.CharField(source='get_status_display', read_only=True)
#     final_amount = serializers.DecimalField(max_digits=17, decimal_places=2, read_only=True)
#     amount_paid = serializers.DecimalField(max_digits=17, decimal_places=2, read_only=True)
#
#     class Meta:
#         model = Sale
#         fields = [
#             'id', 'seller_username', 'customer_name', 'kassa_name',
#             'final_amount', 'amount_paid',
#             'payment_type', 'payment_type_display', 'status', 'status_display', 'created_at'
#         ]
#
#
# class SaleDetailSerializer(SaleListSerializer):
#     items = SaleItemSerializer(many=True, read_only=True)
#     seller = UserSerializer(read_only=True)
#     customer = CustomerSerializer(read_only=True)
#     kassa = KassaSerializer(read_only=True)
#
#     class Meta(SaleListSerializer.Meta):
#         fields = SaleListSerializer.Meta.fields + [
#             'items', 'seller', 'customer', 'kassa'
#         ]
#
#
# class SaleItemInputSerializer(serializers.Serializer):
#     product_id = serializers.PrimaryKeyRelatedField(
#         queryset=Product.objects.filter(is_active=True),
#         label="Mahsulot ID"
#     )
#     quantity = serializers.IntegerField(min_value=1, label="Miqdor")
#     price = serializers.DecimalField(
#         max_digits=17, decimal_places=2,
#         required=True,
#         label="Mahsulot narxi (sotuvchi tushib berilgan narx)"
#     )
#
#     def validate(self, data):
#         product = data['product_id']
#         price = data['price']
#
#         # Agar narx 0 dan kichik yoki 0 bo'lsa xato berish
#         if price <= 0:
#             raise serializers.ValidationError({"price": "Narx 0 dan katta bo'lishi kerak."})
#
#         return data
#
# class NewCustomerInputSerializer(serializers.Serializer):
#     phone_number = serializers.CharField(max_length=20, required=True)
#     full_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
#     address = serializers.CharField(required=False, allow_blank=True, default='')
#
#
# class SaleCreateSerializer(serializers.Serializer):
#     items = SaleItemInputSerializer(many=True, required=True, min_length=1)
#     payment_type = serializers.ChoiceField(choices=Sale.PaymentType.choices)
#     kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.filter(is_active=True))
#     currency = serializers.ChoiceField(choices=Sale.SaleCurrency.choices)
#     customer_id = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), required=False, allow_null=True)
#     new_customer = NewCustomerInputSerializer(required=False, allow_null=True)
#
#     installment_down_payment = serializers.DecimalField(required=False, default=Decimal(0), min_value=Decimal(0),
#                                                         max_digits=17, decimal_places=2)
#     installment_interest_rate = serializers.DecimalField(required=False, default=Decimal(0), min_value=Decimal(0),
#                                                          max_digits=5, decimal_places=2)
#     installment_term_months = serializers.IntegerField(required=False, allow_null=True, min_value=1)
#
#
#
#     def validate(self, data):  # Bu metod avvalgi javobdagi TO'G'RI variantida bo'lishi kerak
#         items = data.get('items')
#         currency = data.get('currency')
#         payment_type = data.get('payment_type')
#         customer_id = data.get('customer_id')
#         new_customer_data = data.get('new_customer')
#
#         if not items: raise serializers.ValidationError({"items": ["Mahsulotlar ro'yxati bo'sh bo'lishi mumkin emas."]})
#         if not currency: raise serializers.ValidationError({"currency": ["Sotuv valyutasi ko'rsatilishi shart."]})
#
#         if customer_id and new_customer_data:
#             raise serializers.ValidationError("Faqat 'customer_id' yoki 'new_customer' dan biri kiritilishi mumkin.")
#         if not customer_id and not new_customer_data and payment_type == Sale.PaymentType.INSTALLMENT:
#             raise serializers.ValidationError("Nasiya uchun mijoz tanlanishi yoki yangi mijoz kiritilishi shart.")
#
#         calculated_original_total = Decimal(0)
#         calculated_final_total = Decimal(0)
#         for item_data in items:
#             product = item_data['product_id']
#             quantity = item_data['quantity']
#             final_price_for_item = item_data['price']  # TO'G'RI NOM
#             original_price = product.price_uzs if currency == Sale.SaleCurrency.UZS else product.price_usd
#             if original_price is None or original_price < 0:
#                 raise serializers.ValidationError(f"'{product.name}' uchun ({currency}) asl narx noto'g'ri.")
#             if final_price_for_item < 0:
#                 raise serializers.ValidationError(f"'{product.name}' uchun yakuniy narx manfiy bo'lishi mumkin emas.")
#             calculated_original_total += original_price * quantity
#             calculated_final_total += final_price_for_item * quantity
#
#         if calculated_final_total <= 0 and payment_type != Sale.PaymentType.INSTALLMENT:
#             raise serializers.ValidationError("Sotuvning yakuniy summasi 0 dan katta bo'lishi kerak.")
#
#         self.context['calculated_original_total_in_currency'] = calculated_original_total
#         self.context['calculated_final_total_in_currency'] = calculated_final_total
#
#         if payment_type == Sale.PaymentType.INSTALLMENT:
#             term_months = data.get('installment_term_months')
#             down_payment = data.get('installment_down_payment', Decimal(0))
#             # Nasiya uchun asos calculated_final_total bo'ladi
#             initial_amount_for_installment = calculated_final_total
#             if not term_months or term_months < 1:
#                 raise serializers.ValidationError(
#                     {"installment_term_months": ["Nasiya muddati 1 oydan kam bo'lmasligi kerak."]})
#             if down_payment > initial_amount_for_installment:
#                 raise serializers.ValidationError({"installment_down_payment": [
#                     f"Boshlang'ich to'lov ({down_payment}) nasiya summasidan ({initial_amount_for_installment}) oshmasligi kerak."]})
#             data['installment_initial_amount'] = initial_amount_for_installment  # Bu create da ishlatiladi
#         return data
#
#     @transaction.atomic
#     def create(self, validated_data):
#         from installments.serializers import InstallmentPlanCreateSerializer
#
#         request = self.context.get('request')
#         user = validated_data.pop('user', request.user if request else None)
#         items_data = validated_data.pop('items')
#         kassa = validated_data.pop('kassa_id')
#         payment_type = validated_data.pop('payment_type')
#         currency = validated_data.pop('currency')
#         customer_id_obj = validated_data.pop('customer_id', None)
#         new_customer_data = validated_data.pop('new_customer', None)
#
#         installment_down_payment = validated_data.pop('installment_down_payment', Decimal(0))
#         installment_interest_rate = validated_data.pop('installment_interest_rate', Decimal(0))
#         installment_term_months = validated_data.pop('installment_term_months', None)
#         # Bu `validate` metodida `data`ga qo'shilgan edi, shuning uchun `validated_data`da bo'ladi
#         installment_initial_amount_for_plan = validated_data.pop('installment_initial_amount',
#                                                                  self.context.get('calculated_final_total_in_currency'))
#
#         customer_for_sale = customer_id_obj
#         if not customer_for_sale and new_customer_data:
#             phone = new_customer_data.get('phone_number')
#             if not phone: raise ValidationError(
#                 {"new_customer.phone_number": "Yangi mijoz uchun telefon raqami majburiy."})
#             customer_for_sale, _ = Customer.objects.get_or_create(
#                 phone_number=phone,
#                 defaults={'full_name': new_customer_data.get('full_name', f"Mijoz {phone}"),
#                           'address': new_customer_data.get('address')}
#             )
#
#         original_total = self.context.get('calculated_original_total_in_currency')
#         final_total_for_sale = self.context.get('calculated_final_total_in_currency')
#
#         if original_total is None or final_total_for_sale is None:
#             raise ValidationError("Sotuv summalari validatsiyada hisoblanmagan (contextda yo'q).")
#
#         amount_to_register_as_paid = final_total_for_sale
#         if payment_type == Sale.PaymentType.INSTALLMENT:
#             amount_to_register_as_paid = installment_down_payment
#
#         sale = Sale.objects.create(
#             seller=user, customer=customer_for_sale, kassa=kassa, currency=currency,
#             original_total_amount_currency=original_total,
#             final_amount_currency=final_total_for_sale,
#             amount_actually_paid_at_sale=amount_to_register_as_paid,
#             payment_type=payment_type, status=Sale.SaleStatus.COMPLETED
#         )
#
#         for item_data_loop in items_data:
#             product = item_data_loop['product_id']
#             quantity = item_data_loop['quantity']
#             final_price_for_item_in_sale_currency = item_data_loop['price']
#
#             price_usd_to_save = None
#             price_uzs_to_save = None
#
#             if currency == Sale.SaleCurrency.UZS:
#                 price_uzs_to_save = final_price_for_item_in_sale_currency
#                 # Agar USD narxini ham saqlamoqchi bo'lsak (ma'lumot uchun, lekin bu asl narx bo'ladi)
#                 # price_usd_to_save = product.price_usd
#             elif currency == Sale.SaleCurrency.USD:
#                 price_usd_to_save = final_price_for_item_in_sale_currency
#                 # price_uzs_to_save = product.price_uzs
#
#             SaleItem.objects.create(
#                 sale=sale,
#                 product=product,
#                 quantity=quantity,
#                 price_at_sale_usd=price_usd_to_save,  # MODELINGIZDAGI MAVJUD MAYDON
#                 price_at_sale_uzs=price_uzs_to_save  # MODELINGIZDAGI MAVJUD MAYDON
#             )
#             # Ombor logikasi
#             try:
#                 stock = ProductStock.objects.select_for_update().get(product=product, kassa=kassa)
#                 if stock.quantity < quantity: raise ValidationError(f"{product.name} uchun qoldiq yetarli emas.")
#                 stock.quantity -= quantity
#                 stock.save(update_fields=['quantity'])
#             except ProductStock.DoesNotExist:
#                 raise ValidationError(f"{product.name} uchun {kassa.name} da ombor yozuvi topilmadi.")
#
#             InventoryOperation.objects.create(product=product, kassa=kassa, user=user, quantity=-quantity,
#                                               operation_type=InventoryOperation.OperationType.SALE,
#                                               comment=f"Sotuv #{sale.id}")
#
#         if currency == Sale.SaleCurrency.UZS and amount_to_register_as_paid > 0:
#             kassa_trans_type = KassaTransaction.TransactionType.SALE
#             if payment_type == Sale.PaymentType.INSTALLMENT:
#                 kassa_trans_type = KassaTransaction.TransactionType.INSTALLMENT_PAYMENT
#             KassaTransaction.objects.create(
#                 kassa=kassa, amount=amount_to_register_as_paid,
#                 transaction_type=kassa_trans_type, user=user,
#                 comment=f"Sotuv #{sale.id}", related_sale=sale
#             )
#
#         if payment_type == Sale.PaymentType.INSTALLMENT:
#             if installment_initial_amount_for_plan is None or installment_initial_amount_for_plan <= 0:
#                 raise ValidationError("Nasiya uchun asosiy summa 0 dan katta bo'lishi shart.")
#             if installment_term_months is None:
#                 raise ValidationError("Nasiya muddati kiritilishi shart.")
#
#             installment_plan_data = {
#                 'sale': sale.pk, 'customer': customer_for_sale.pk, 'currency': currency,
#                 'initial_amount': installment_initial_amount_for_plan,
#                 'down_payment': installment_down_payment,
#                 'interest_rate': installment_interest_rate,
#                 'term_months': installment_term_months,
#             }
#             plan_serializer = InstallmentPlanCreateSerializer(data=installment_plan_data, context=self.context)
#             if plan_serializer.is_valid(raise_exception=True):
#                 plan_serializer.save()
#
#         return sale
#
#
#
# class SaleReturnItemInputSerializer(serializers.Serializer):
#     sale_item_id = serializers.PrimaryKeyRelatedField(queryset=SaleItem.objects.all(), label="Sotuv Elementi ID")
#     quantity = serializers.IntegerField(min_value=1, label="Qaytariladigan miqdor")
#
# class SaleReturnSerializer(serializers.Serializer):
#     items_to_return = SaleReturnItemInputSerializer(many=True, required=True, min_length=1, label="Qaytariladigan mahsulotlar")
#     reason = serializers.CharField(required=False, allow_blank=True, label="Qaytarish sababi")
#
#     def validate_items_to_return(self, items):
#         # ... (bu metod o'zgarishsiz qoladi) ...
#         if not items:
#             raise serializers.ValidationError("Qaytarish uchun kamida bitta mahsulot tanlang.")
#         sale_id = None
#         sale_items_map = {}
#         for item_data in items:
#             sale_item_id = item_data['sale_item_id'].id
#             quantity_to_return = item_data['quantity']
#             try:
#                 sale_item = SaleItem.objects.select_related('sale__kassa', 'product').get(id=sale_item_id) # kassani ham olish
#                 sale_items_map[sale_item_id] = sale_item
#             except SaleItem.DoesNotExist:
#                 raise serializers.ValidationError({f"items_to_return[{items.index(item_data)}].sale_item_id": f"ID={sale_item_id} bilan sotuv elementi topilmadi."})
#
#             current_sale_id = sale_item.sale_id
#             if sale_id is None:
#                 sale_id = current_sale_id
#                 sale = sale_item.sale # Sotuvni olish
#                 if not sale.can_be_returned: # Bu yerda tekshirish
#                     raise serializers.ValidationError(f"Ushbu sotuv '{sale.get_status_display()}' holatida, qaytarib bo'lmaydi.")
#                 self.context['sale_instance'] = sale
#             elif current_sale_id != sale_id:
#                 raise serializers.ValidationError("Barcha qaytariladigan mahsulotlar bir xil sotuvga tegishli bo'lishi kerak.")
#
#             if quantity_to_return > sale_item.quantity_available_to_return:
#                  raise serializers.ValidationError(
#                      f"'{sale_item.product.name}' uchun faqat {sale_item.quantity_available_to_return} dona qaytarish mumkin "
#                      f"(so'ralgan: {quantity_to_return})."
#                  )
#         self.context['sale_items_to_process'] = sale_items_map
#         return items
#
#     @transaction.atomic
#     def create(self, validated_data):
#         # --- Importni shu metod ichiga ko'chirdik ---
#         from installments.models import InstallmentPlan
#         # ------------------------------------------
#         from .models import SaleReturn # SaleReturn modelini import qilish
#         from .models import SaleReturnItem # SaleReturnItem modelini import qilish
#
#         items_data = validated_data['items_to_return']
#         reason = validated_data.get('reason')
#         user = validated_data['user']
#         sale = self.context['sale_instance']
#         sale_items_map = self.context['sale_items_to_process']
#         kassa = sale.kassa
#
#         total_returned_amount_uzs = 0
#         inventory_ops_to_create = []
#         sale_items_to_update = []
#         product_stock_updates = {}
#
#         # --- Qaytarish operatsiyasini yaratish (avval SaleReturn kerak) ---
#         sale_return_obj = SaleReturn.objects.create(
#             original_sale=sale,
#             reason=reason,
#             returned_by=user
#             # total_returned_amount_uzs keyin hisoblanadi
#         )
#         # ---------------------------------------------------------------
#
#         for item_data in items_data:
#             sale_item_id = item_data['sale_item_id'].id
#             quantity_returned = item_data['quantity']
#             sale_item = sale_items_map[sale_item_id]
#
#             # --- SaleReturnItem yaratish ---
#             SaleReturnItem.objects.create(
#                 sale_return=sale_return_obj, # Yaratilgan qaytarish obyektiga bog'lash
#                 sale_item=sale_item,
#                 quantity_returned=quantity_returned
#             )
#             # -----------------------------
#
#             sale_item.quantity_returned += quantity_returned
#             sale_items_to_update.append(sale_item)
#
#             product_id = sale_item.product_id
#             if product_id not in product_stock_updates:
#                  product_stock_updates[product_id] = 0
#             product_stock_updates[product_id] += quantity_returned
#
#             inventory_ops_to_create.append(InventoryOperation(
#                 product=sale_item.product, kassa=kassa, user=user,
#                 quantity=quantity_returned, # Musbat
#                 operation_type=InventoryOperation.OperationType.RETURN,
#                 comment=f"Sotuv #{sale.id} uchun qaytarish #{sale_return_obj.id}. Sabab: {reason or '-'}",
#             ))
#
#             total_returned_amount_uzs += sale_item.price_at_sale_uzs * quantity_returned
#
#         # --- Qaytarilgan summani SaleReturn ga yozish ---
#         sale_return_obj.total_returned_amount_uzs = total_returned_amount_uzs
#         sale_return_obj.save()
#         # ---------------------------------------------
#
#         stocks_to_update = ProductStock.objects.select_for_update().filter(
#             product_id__in=product_stock_updates.keys(), kassa=kassa
#         )
#         for stock in stocks_to_update:
#             stock.quantity += product_stock_updates[stock.product_id]
#         ProductStock.objects.bulk_update(stocks_to_update, ['quantity'])
#         InventoryOperation.objects.bulk_create(inventory_ops_to_create)
#         SaleItem.objects.bulk_update(sale_items_to_update, ['quantity_returned'])
#
#         all_items_returned = all(si.quantity_available_to_return == 0 for si in sale.items.all())
#         if all_items_returned:
#             sale.status = Sale.SaleStatus.RETURNED # SaleStatus ni Sale modelidan olamiz
#         else:
#             sale.status = Sale.SaleStatus.PARTIALLY_RETURNED # SaleStatus ni Sale modelidan olamiz
#         sale.save(update_fields=['status'])
#
#         if sale.payment_type == Sale.PaymentType.INSTALLMENT:
#             try:
#                 plan = sale.installmentplan
#                 plan.adjust_for_return(total_returned_amount_uzs)
#                 plan.save()
#                 print(f"Installment plan {plan.id} adjusted for return.")
#             except InstallmentPlan.DoesNotExist:
#                 print(f"ERROR: Installment plan not found for returned sale {sale.id}.")
#             except Exception as e:
#                 print(f"Error adjusting installment plan for returned sale {sale.id}: {e}")
#
#         if total_returned_amount_uzs > 0:
#             KassaTransaction.objects.create(
#                 kassa=kassa,
#                 amount=total_returned_amount_uzs,
#                 transaction_type=KassaTransaction.TransactionType.RETURN_REFUND,
#                 user=user,
#                 comment=f"Sotuv #{sale.id} uchun qaytarish #{sale_return_obj.id}",
#                 related_return=sale_return_obj
#             )
#
#         updated_sale_serializer = SaleDetailSerializer(instance=sale, context=self.context)
#         return updated_sale_serializer.data
#
#
#
# # --- Qaytarish detallarini ko'rsatish uchun serializer (qo'shimcha) ---
# class SaleReturnItemDetailSerializer(serializers.ModelSerializer):
#      # Qaytarilgan element haqida ma'lumot
#      product_name = serializers.CharField(source='sale_item.product.name', read_only=True)
#      price_at_sale_uzs = serializers.DecimalField(source='sale_item.price_at_sale_uzs', max_digits=15, decimal_places=2, read_only=True)
#
#      class Meta:
#          model = SaleReturnItem
#          fields = ['id', 'product_name', 'quantity_returned', 'price_at_sale_uzs']
#
# class SaleReturnDetailSerializer(serializers.ModelSerializer):
#      # To'liq qaytarish operatsiyasi haqida ma'lumot
#      original_sale_id = serializers.IntegerField(source='original_sale.id', read_only=True)
#      returned_by_username = serializers.CharField(source='returned_by.username', read_only=True, default=None)
#      items = SaleReturnItemDetailSerializer(many=True, read_only=True) # Qaytarilgan elementlar
#
#      class Meta:
#          model = SaleReturn
#          fields = ['id', 'original_sale_id', 'reason', 'returned_by_username', 'created_at', 'total_returned_amount_uzs', 'items']
#
#
# class PosProductSerializer(serializers.ModelSerializer):
#     """POS ekrani uchun mahsulot ma'lumotlari (qoldiq bilan)"""
#     category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
#     price_uzs = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
#     quantity_in_stock = serializers.IntegerField(read_only=True, default=0)
#
#     class Meta:
#         model = Product
#         fields = [
#             'id', 'name', 'barcode',
#             'category_name', 'price_uzs', 'price_usd',
#             'quantity_in_stock',
#         ]
#         # ---- Tekshiring ----
#         read_only_fields = [ # LIST YOKI KORTEJ
#             'id', 'name', 'barcode', 'category_name',
#             'price_uzs', 'price_usd', 'quantity_in_stock'
#         ]
#
#
# class KassaTransactionSerializer(serializers.ModelSerializer):
#     """Kassa amaliyotlarini ko'rsatish uchun"""
#     kassa_name = serializers.CharField(source='kassa.name', read_only=True)
#     user_username = serializers.CharField(source='user.username', read_only=True, allow_null=True)
#     transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
#     related_sale_id = serializers.PrimaryKeyRelatedField(source='related_sale', read_only=True)
#     related_payment_id = serializers.PrimaryKeyRelatedField(source='related_installment_payment', read_only=True)
#     related_return_id = serializers.PrimaryKeyRelatedField(source='related_return', read_only=True)
#
#     class Meta:
#         model = KassaTransaction
#         fields = [
#             'id', 'kassa', 'kassa_name', 'amount', 'transaction_type', 'transaction_type_display',
#             'user', 'user_username', 'comment', 'timestamp',
#             'related_sale_id', 'related_payment_id', 'related_return_id'
#         ]
#         read_only_fields = fields # Odatda o'zgartirilmaydi
#
# class BaseCashOperationSerializer(serializers.Serializer):
#     """Kirim/Chiqim uchun asosiy serializer"""
#     kassa_id = serializers.PrimaryKeyRelatedField(
#         queryset=Kassa.objects.filter(is_active=True),
#         label="Kassa"
#     )
#     amount = serializers.DecimalField(
#         max_digits=17, decimal_places=2, min_value=Decimal('0.01'),
#         label="Summa (UZS)"
#     )
#     comment = serializers.CharField(required=False, allow_blank=True, label="Izoh")
#
#     def validate_kassa_id(self, kassa):
#         # Qo'shimcha tekshiruvlar (masalan, user shu kassaga kira oladimi?)
#         # permission_classes hal qilishi kerak
#         return kassa
#
# class CashInSerializer(BaseCashOperationSerializer):
#     """Kassaga naqd pul kirimi uchun"""
#     def save(self, **kwargs):
#         validated_data = {**self.validated_data, **kwargs}
#         kassa = validated_data['kassa_id']
#         amount = validated_data['amount']
#         comment = validated_data.get('comment')
#         user = validated_data['user'] # Viewdan keladi
#
#         transaction = KassaTransaction.objects.create(
#             kassa=kassa,
#             amount=amount,
#             transaction_type=KassaTransaction.TransactionType.CASH_IN,
#             user=user,
#             comment=comment
#         )
#         return transaction
#
# class CashOutSerializer(BaseCashOperationSerializer):
#     """Kassadan naqd pul chiqimi (xarajat) uchun"""
#     def save(self, **kwargs):
#         validated_data = {**self.validated_data, **kwargs}
#         kassa = validated_data['kassa_id']
#         amount = validated_data['amount']
#         comment = validated_data.get('comment')
#         user = validated_data['user']
#
#         # Balansni tekshirish (ixtiyoriy, lekin tavsiya etiladi)
#         # current_balance = get_kassa_balance(kassa.id) # reports.services dan import qilish kerak
#         # if current_balance is None or amount > current_balance:
#         #     raise serializers.ValidationError(f"{kassa.name} kassasida yetarli mablag' yo'q (Mavjud: {current_balance:.2f} UZS).")
#
#         transaction = KassaTransaction.objects.create(
#             kassa=kassa,
#             amount=amount, # Summa musbat saqlanadi, turi chiqimligini bildiradi
#             transaction_type=KassaTransaction.TransactionType.CASH_OUT,
#             user=user,
#             comment=comment
#         )
#         return transaction
#
# # SaleReturnSerializer ga refund_method qo'shish
# class SaleReturnItemInputSerializer(serializers.Serializer):
#     sale_item_id = serializers.PrimaryKeyRelatedField(queryset=SaleItem.objects.all(), label="Sotuv Elementi ID")
#     quantity = serializers.IntegerField(min_value=1, label="Qaytariladigan miqdor")
#
# class SaleReturnSerializer(serializers.Serializer):
#     items_to_return = SaleReturnItemInputSerializer(many=True, required=True, min_length=1, label="Qaytariladigan mahsulotlar")
#     reason = serializers.CharField(required=False, allow_blank=True, label="Qaytarish sababi")
#     # Qaytarish usulini qo'shamiz
#     refund_method = serializers.ChoiceField(
#         choices=[('Naqd', 'Naqd Pul'), ('Karta', 'Kartaga'), ('None', "Pul qaytarilmaydi")], # Yoki boshqa variantlar
#         default='Naqd', # Standart holatda naqd qaytariladi deb hisoblaymiz
#         label="Pulni Qaytarish Usuli"
#     )
#
#     def validate_items_to_return(self, items):
#         # ... (oldingi validatsiya logikasi: bitta sotuv, yetarli miqdor) ...
#         if not items: raise serializers.ValidationError("...")
#         sale_id = None
#         sale_items_map = {}
#         for item_data in items:
#             sale_item_id = item_data['sale_item_id'].id
#             quantity_to_return = item_data['quantity']
#             try:
#                 sale_item = SaleItem.objects.select_related('sale__kassa', 'product').get(id=sale_item_id)
#                 sale_items_map[sale_item_id] = sale_item
#             except SaleItem.DoesNotExist: raise serializers.ValidationError(...)
#
#             current_sale_id = sale_item.sale_id
#             if sale_id is None:
#                 sale_id = current_sale_id
#                 sale = sale_item.sale
#                 if not sale.can_be_returned: raise serializers.ValidationError(...)
#                 self.context['sale_instance'] = sale
#             elif current_sale_id != sale_id: raise serializers.ValidationError(...)
#             if quantity_to_return > sale_item.quantity_available_to_return: raise serializers.ValidationError(...)
#         self.context['sale_items_to_process'] = sale_items_map
#         return items
#
#     @transaction.atomic
#     def create(self, validated_data):
#         # --- Importlar ---
#         from installments.models import InstallmentPlan # Faqat kerak bo'lsa
#         from decimal import Decimal
#
#         items_data = validated_data['items_to_return']
#         reason = validated_data.get('reason')
#         refund_method = validated_data['refund_method'] # Qaytarish usuli
#         user = validated_data['user'] # Viewdan keladi
#         sale = self.context['sale_instance']
#         sale_items_map = self.context['sale_items_to_process']
#         kassa = sale.kassa
#
#         total_returned_amount_uzs = Decimal(0)
#         inventory_ops_to_create = []
#         sale_items_to_update = []
#         product_stock_updates = {}
#
#         sale_return_obj = SaleReturn.objects.create(
#             original_sale=sale, reason=reason, returned_by=user
#         )
#
#         for item_data in items_data:
#             sale_item_id = item_data['sale_item_id'].id
#             quantity_returned = item_data['quantity']
#             sale_item = sale_items_map[sale_item_id]
#
#             SaleReturnItem.objects.create(
#                 sale_return=sale_return_obj, sale_item=sale_item, quantity_returned=quantity_returned
#             )
#
#             sale_item.quantity_returned += quantity_returned
#             sale_items_to_update.append(sale_item)
#
#             product_id = sale_item.product_id
#             product_stock_updates[product_id] = product_stock_updates.get(product_id, 0) + quantity_returned
#
#             inventory_ops_to_create.append(InventoryOperation(
#                 product=sale_item.product, kassa=kassa, user=user, quantity=quantity_returned,
#                 operation_type=InventoryOperation.OperationType.RETURN,
#                 comment=f"Sotuv #{sale.id} qaytarish #{sale_return_obj.id}. Sabab: {reason or '-'}",
#             ))
#             total_returned_amount_uzs += sale_item.price_at_sale_uzs * quantity_returned
#
#         sale_return_obj.total_returned_amount_uzs = total_returned_amount_uzs
#         sale_return_obj.save()
#
#         # Ombor qoldiqlarini yangilash
#         stocks_to_update = ProductStock.objects.select_for_update().filter(
#             product_id__in=product_stock_updates.keys(), kassa=kassa
#         )
#         for stock in stocks_to_update:
#             stock.quantity += product_stock_updates[stock.product_id]
#         ProductStock.objects.bulk_update(stocks_to_update, ['quantity'])
#
#         # Operatsiya tarixini saqlash
#         InventoryOperation.objects.bulk_create(inventory_ops_to_create)
#         # Sotuv elementi qaytarilgan miqdorini saqlash
#         SaleItem.objects.bulk_update(sale_items_to_update, ['quantity_returned'])
#
#         # Sotuv statusini yangilash
#         all_items = sale.items.all() # Barcha elementlarni olish
#         if all(si.quantity_available_to_return == 0 for si in all_items):
#             sale.status = Sale.SaleStatus.RETURNED
#         else:
#             sale.status = Sale.SaleStatus.PARTIALLY_RETURNED
#         sale.save(update_fields=['status'])
#
#         # Nasiya rejasini moslashtirish (agar bo'lsa)
#         if sale.payment_type == Sale.PaymentType.INSTALLMENT:
#             try:
#                 plan = sale.installmentplan
#                 plan.adjust_for_return(total_returned_amount_uzs)
#                 plan.save()
#             except InstallmentPlan.DoesNotExist: pass # Xatolik bermaymiz
#             except Exception as e: print(f"Error adjusting installment: {e}")
#
#         # Kassaga qaytarilgan summani chiqim qilish (agar Naqd qaytarilgan bo'lsa)
#         if refund_method == 'Naqd' and total_returned_amount_uzs > 0:
#              KassaTransaction.objects.create(
#                  kassa=kassa,
#                  amount=total_returned_amount_uzs,
#                  transaction_type=KassaTransaction.TransactionType.RETURN_REFUND,
#                  user=user,
#                  comment=f"Sotuv #{sale.id} uchun qaytarish #{sale_return_obj.id}",
#                  related_return=sale_return_obj
#              )
#
#         # Javob sifatida yangilangan sotuv detalini qaytaramiz
#         return SaleDetailSerializer(instance=sale, context=self.context).data

# sales/serializers.py
from decimal import Decimal

from django.core.validators import RegexValidator
from django.utils import timezone
from rest_framework import serializers
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.validators import UniqueValidator

# Modellarni import qilish
from .models import Customer, Sale, SaleItem, KassaTransaction, SaleReturn, SaleReturnItem
from products.models import Product, Kassa
from inventory.models import ProductStock, InventoryOperation
# Serializerlarni import qilish
from products.serializers import ProductSerializer as ProductListSerializer, \
    KassaSerializer  # ProductSerializer ni ProductListSerializer deb nomladik chalkashmaslik uchun
from users.serializers import UserSerializer
# Installments
from installments.models import InstallmentPlan


# from installments.serializers import InstallmentPlanCreateSerializer # Buni SaleCreateSerializer.create() ichiga ko'chiramiz

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'full_name', 'phone_number', 'email', 'address', 'created_at']
        read_only_fields = ('created_at',)
        extra_kwargs = {
            'phone_number': {
                'validators': [
                    UniqueValidator(
                        queryset=Customer.objects.all(),
                        message="Bu telefon raqami bilan mijoz allaqachon mavjud."
                    ),
                    # YANGI QO'SHILDI: Telefon raqami formati uchun validator
                    RegexValidator(
                        regex=r'^\+998\d{9}$', # +998 va 9 ta raqam
                        message="Telefon raqami +998XXXXXXXXX formatida bo'lishi kerak (masalan, +998901234567)."
                    )
                ]
            }
        }


class SaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    # YANGI QO'SHILDI: Mahsulotning shtrix-kodi/IMEI si
    product_barcode = serializers.CharField(source='product.barcode', read_only=True, allow_null=True)

    class Meta:
        model = SaleItem
        fields = [
            'product_name',
            'product_barcode', # YANGI
            'quantity',
            'price_at_sale_uzs', # Bu SaleItem dagi narx, sotuv valyutasiga mos kelishi uchun
            'price_at_sale_usd'  # Bu SaleItem dagi narx
        ]


class SaleListSerializer(serializers.ModelSerializer):
    seller_username = serializers.CharField(source='seller.username', read_only=True, allow_null=True)
    customer_name = serializers.CharField(source='customer.full_name', read_only=True, allow_null=True)
    kassa_name = serializers.CharField(source='kassa.name', read_only=True)
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    items_summary = SaleItemSerializer(source='items', many=True,
                                              read_only=True)  # Bu o'zgarmaydi, chunki SaleItemForListSerializer o'zgartirildi

    class Meta:
        model = Sale
        fields = [
            'id', 'seller_username', 'customer_name', 'kassa_name',
            'currency',
            'final_amount_currency',
            'amount_actually_paid_at_sale',
            'payment_type', 'payment_type_display', 'status', 'status_display', 'created_at',
            'items_summary'
        ]


class SaleDetailSerializer(SaleListSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    seller = UserSerializer(read_only=True, allow_null=True)
    customer = CustomerSerializer(read_only=True, allow_null=True)
    kassa = KassaSerializer(read_only=True)
    discount_amount_currency = serializers.ReadOnlyField()  # Property dan

    class Meta(SaleListSerializer.Meta):
        fields = SaleListSerializer.Meta.fields + [
            'items', 'seller', 'customer', 'kassa',
            'original_total_amount_currency',  # Chegirmasiz asl summa
            'discount_amount_currency'  # Hisoblangan chegirma
        ]


class SaleItemInputSerializer(serializers.Serializer):
    # ... (o'zgarishsiz)
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(is_active=True),
                                                    label="Mahsulot ID")
    quantity = serializers.IntegerField(min_value=1, label="Miqdor")
    price = serializers.DecimalField(max_digits=17, decimal_places=2, required=True,
                                     label="Mahsulot narxi (sotuvchi tushib berilgan narx)")

    def validate(self, data):
        product = data['product_id'];
        price = data['price']
        if price <= 0: raise serializers.ValidationError({"price": "Narx 0 dan katta bo'lishi kerak."})
        return data


class NewCustomerInputSerializer(serializers.Serializer):
    # ... (o'zgarishsiz)
    phone_number = serializers.CharField(max_length=20, required=True)
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    address = serializers.CharField(required=False, allow_blank=True, default='')


class SaleCreateSerializer(serializers.Serializer):
    items = SaleItemInputSerializer(many=True, required=True, min_length=1)
    payment_type = serializers.ChoiceField(choices=Sale.PaymentType.choices)
    kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.filter(is_active=True))
    currency = serializers.ChoiceField(choices=Sale.SaleCurrency.choices)

    # Mijoz endi har doim ixtiyoriy
    customer_id = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), required=False, allow_null=True)
    new_customer = NewCustomerInputSerializer(required=False, allow_null=True)

    installment_down_payment = serializers.DecimalField(required=False, default=Decimal(0), min_value=Decimal(0),
                                                        max_digits=17, decimal_places=2)
    installment_interest_rate = serializers.DecimalField(required=False, default=Decimal(0), min_value=Decimal(0),
                                                         max_digits=5, decimal_places=2)
    installment_term_months = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate(self, data):
        items = data.get('items')
        sale_currency_code = data.get('currency')
        payment_type = data.get('payment_type')
        customer_id = data.get('customer_id')
        new_customer_data = data.get('new_customer')

        # --- MIJOZNI TEKSHIRISH (O'ZGARTIRILDI: Barcha majburiylik olib tashlandi) ---
        if customer_id and new_customer_data:
            raise serializers.ValidationError("Faqat 'customer_id' yoki 'new_customer' dan biri kiritilishi mumkin.")

        # Agar yangi mijoz kiritilayotgan bo'lsa, telefon raqami majburiyligi qolishi mumkin (agar kerak bo'lsa)
        # Yoki buni ham ixtiyoriy qilish mumkin. Hozircha qoldiramiz.
        if new_customer_data and not new_customer_data.get('phone_number'):
            # Agar telefon raqami yangi mijoz uchun muhim bo'lsa, bu xatolik qoladi.
            # Agar u ham ixtiyoriy bo'lsa, bu shartni olib tashlang.
            # Mijozning talabiga ko'ra, bu ham ixtiyoriy bo'lishi mumkin.
            # Hozircha, yangi mijoz uchun telefon raqami kerak deb hisoblaymiz,
            # aks holda uni Customer sifatida saqlash qiyin.
            # Agar telefon raqami umuman ixtiyoriy bo'lsa, Customer modelidagi unique=True ni ham o'zgartirish kerak.
            # Eng yaxshisi, yangi mijoz uchun telefon raqamini majburiy qoldirish.
            # Agar "yangi mijoz" tanlanmasa (bo'sh qoldirilsa), muammo yo'q.
            raise serializers.ValidationError(
                {"new_customer": {"phone_number": ["Yangi mijoz uchun telefon raqami majburiy."]}})
        # --- MIJOZNI TEKSHIRISH TUGADI ---

        if not items: raise serializers.ValidationError({"items": ["Mahsulotlar ro'yxati bo'sh bo'lishi mumkin emas."]})
        if not sale_currency_code: raise serializers.ValidationError(
            {"currency": ["Sotuv valyutasi ko'rsatilishi shart."]})

        # ... (qolgan validatsiya logikasi o'zgarishsiz) ...
        calculated_original_total = Decimal(0);
        calculated_final_total = Decimal(0)
        for item_data in items:
            product = item_data['product_id'];
            quantity = item_data['quantity'];
            final_price_for_item = item_data['price']
            original_price = product.price_uzs if sale_currency_code == Sale.SaleCurrency.UZS else product.price_usd
            if original_price is None or original_price < 0: raise serializers.ValidationError(
                f"'{product.name}' uchun ({sale_currency_code}) asl narx noto'g'ri.")
            if final_price_for_item < 0: raise serializers.ValidationError(
                f"'{product.name}' uchun yakuniy narx manfiy bo'lishi mumkin emas.")
            calculated_original_total += original_price * quantity;
            calculated_final_total += final_price_for_item * quantity
        if calculated_final_total <= 0 and payment_type != Sale.PaymentType.INSTALLMENT: raise serializers.ValidationError(
            "Sotuvning yakuniy summasi 0 dan katta bo'lishi kerak (naqd/karta uchun).")
        self.context['calculated_original_total_in_currency'] = calculated_original_total
        self.context['calculated_final_total_in_currency'] = calculated_final_total
        if payment_type == Sale.PaymentType.INSTALLMENT:
            term_months = data.get('installment_term_months');
            down_payment = data.get('installment_down_payment', Decimal(0))
            initial_amount_for_installment = calculated_final_total
            if not term_months or term_months < 1: raise serializers.ValidationError(
                {"installment_term_months": ["Nasiya muddati 1 oydan kam bo'lmasligi kerak."]})
            if down_payment < 0: raise serializers.ValidationError(
                {"installment_down_payment": ["Boshlang'ich to'lov manfiy bo'lishi mumkin emas."]})
            if down_payment > initial_amount_for_installment:
                if initial_amount_for_installment > 0:
                    raise serializers.ValidationError({"installment_down_payment": [
                        f"Boshlang'ich to'lov ({down_payment}) nasiya summasidan ({initial_amount_for_installment}) oshmasligi kerak."]})
                elif down_payment > 0:
                    raise serializers.ValidationError({"installment_down_payment": [
                        "Nasiya summasi 0 bo'lsa, boshlang'ich to'lov ham 0 bo'lishi kerak."]})
            data['installment_initial_amount'] = initial_amount_for_installment
        return data

    # create metodi o'zgarishsiz qoladi
    @transaction.atomic
    def create(self, validated_data):
        # ... (avvalgi kod) ...
        from installments.serializers import InstallmentPlanCreateSerializer
        request = self.context.get('request');
        user = validated_data.pop('user', request.user if request else None);
        items_data = validated_data.pop('items');
        kassa = validated_data.pop('kassa_id');
        payment_type = validated_data.pop('payment_type');
        sale_currency_code = validated_data.pop('currency');
        customer_id_obj = validated_data.pop('customer_id', None);
        new_customer_data = validated_data.pop('new_customer', None);
        installment_down_payment = validated_data.pop('installment_down_payment', Decimal(0));
        installment_interest_rate = validated_data.pop('installment_interest_rate', Decimal(0));
        installment_term_months = validated_data.pop('installment_term_months', None);
        installment_initial_amount_for_plan = validated_data.pop('installment_initial_amount',
                                                                 self.context.get('calculated_final_total_in_currency'))
        customer_for_sale = customer_id_obj
        if not customer_for_sale and new_customer_data: phone = new_customer_data.get(
            'phone_number'); customer_for_sale, _ = Customer.objects.get_or_create(phone_number=phone, defaults={
            'full_name': new_customer_data.get('full_name', f"Mijoz {phone}"),
            'address': new_customer_data.get('address')})
        original_total = self.context.get('calculated_original_total_in_currency');
        final_total_for_sale = self.context.get('calculated_final_total_in_currency');
        if original_total is None or final_total_for_sale is None: raise ValidationError(
            "Sotuv summalari validatsiyada hisoblanmagan.")
        amount_to_register_as_paid = final_total_for_sale
        if payment_type == Sale.PaymentType.INSTALLMENT: amount_to_register_as_paid = installment_down_payment
        sale = Sale.objects.create(seller=user, customer=customer_for_sale, kassa=kassa, currency=sale_currency_code,
                                   original_total_amount_currency=original_total,
                                   final_amount_currency=final_total_for_sale,
                                   amount_actually_paid_at_sale=amount_to_register_as_paid, payment_type=payment_type,
                                   status=Sale.SaleStatus.COMPLETED)
        for item_data_loop in items_data:
            product = item_data_loop['product_id'];
            quantity = item_data_loop['quantity'];
            final_price_for_item_in_sale_currency = item_data_loop['price'];
            price_usd_to_save, price_uzs_to_save = None, None;
            original_price_usd_item, original_price_uzs_item = product.price_usd, product.price_uzs
            if sale_currency_code == Sale.SaleCurrency.UZS:
                price_uzs_to_save = final_price_for_item_in_sale_currency
            elif sale_currency_code == Sale.SaleCurrency.USD:
                price_usd_to_save = final_price_for_item_in_sale_currency
            SaleItem.objects.create(sale=sale, product=product, quantity=quantity, price_at_sale_usd=price_usd_to_save,
                                    price_at_sale_uzs=price_uzs_to_save,
                                    original_price_at_sale_usd_item=original_price_usd_item,
                                    original_price_at_sale_uzs_item=original_price_uzs_item)
            try:
                stock = ProductStock.objects.select_for_update().get(product=product, kassa=kassa)
            except ProductStock.DoesNotExist:
                raise ValidationError(f"{product.name} uchun {kassa.name} da ombor yozuvi topilmadi.")
            if stock.quantity < quantity: raise ValidationError(f"{product.name} uchun qoldiq yetarli emas.")
            stock.quantity -= quantity;
            stock.save(update_fields=['quantity'])
            InventoryOperation.objects.create(product=product, kassa=kassa, user=user, quantity=-quantity,
                                              operation_type=InventoryOperation.OperationType.SALE,
                                              comment=f"Sotuv #{sale.id}")
        if amount_to_register_as_paid > 0:
            kassa_trans_type = KassaTransaction.TransactionType.SALE
            if payment_type == Sale.PaymentType.INSTALLMENT: kassa_trans_type = KassaTransaction.TransactionType.INSTALLMENT_PAYMENT
            KassaTransaction.objects.create(kassa=kassa, currency=sale_currency_code, amount=amount_to_register_as_paid,
                                            transaction_type=kassa_trans_type, user=user,
                                            comment=f"Sotuv #{sale.id} ({sale_currency_code})", related_sale=sale)
        if payment_type == Sale.PaymentType.INSTALLMENT:
            if installment_initial_amount_for_plan is None or installment_initial_amount_for_plan < 0:
                if installment_initial_amount_for_plan is None or installment_initial_amount_for_plan < 0: raise ValidationError(
                    "Nasiya uchun asosiy summa 0 dan kichik bo'lishi mumkin emas.")
            if installment_term_months is None: raise ValidationError("Nasiya muddati kiritilishi shart.")
            installment_plan_data = {'sale': sale.pk, 'customer': customer_for_sale.pk, 'currency': sale_currency_code,
                                     'initial_amount': installment_initial_amount_for_plan,
                                     'down_payment': installment_down_payment,
                                     'interest_rate': installment_interest_rate,
                                     'term_months': installment_term_months, };
            plan_serializer = InstallmentPlanCreateSerializer(data=installment_plan_data, context=self.context)
            if plan_serializer.is_valid(raise_exception=True): plan_serializer.save()
        return sale

# class SaleCreateSerializer(serializers.Serializer):
#     # ... (maydonlar o'zgarishsiz)
#     items = SaleItemInputSerializer(many=True, required=True, min_length=1)
#     payment_type = serializers.ChoiceField(choices=Sale.PaymentType.choices)
#     kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.filter(is_active=True))
#     currency = serializers.ChoiceField(choices=Sale.SaleCurrency.choices)
#     customer_id = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), required=False, allow_null=True)
#     new_customer = NewCustomerInputSerializer(required=False, allow_null=True)
#     installment_down_payment = serializers.DecimalField(required=False, default=Decimal(0), min_value=Decimal(0),
#                                                         max_digits=17, decimal_places=2)
#     installment_interest_rate = serializers.DecimalField(required=False, default=Decimal(0), min_value=Decimal(0),
#                                                          max_digits=5, decimal_places=2)
#     installment_term_months = serializers.IntegerField(required=False, allow_null=True, min_value=1)
#
#     def validate(self, data):
#         # ... (validate logikasi o'zgarishsiz, self.context ga summalarni yozadi)
#         items = data.get('items');
#         currency = data.get('currency');
#         payment_type = data.get('payment_type')
#         customer_id = data.get('customer_id');
#         new_customer_data = data.get('new_customer')
#         if not items: raise serializers.ValidationError({"items": ["Mahsulotlar ro'yxati bo'sh bo'lishi mumkin emas."]})
#         if not currency: raise serializers.ValidationError({"currency": ["Sotuv valyutasi ko'rsatilishi shart."]})
#         if customer_id and new_customer_data: raise serializers.ValidationError(
#             "Faqat 'customer_id' yoki 'new_customer' dan biri kiritilishi mumkin.")
#         if not customer_id and not new_customer_data and payment_type == Sale.PaymentType.INSTALLMENT: raise serializers.ValidationError(
#             "Nasiya uchun mijoz tanlanishi yoki yangi mijoz kiritilishi shart.")
#
#         calculated_original_total = Decimal(0)
#         calculated_final_total = Decimal(0)
#         for item_data in items:
#             product = item_data['product_id'];
#             quantity = item_data['quantity'];
#             final_price_for_item = item_data['price']
#             original_price = product.price_uzs if currency == Sale.SaleCurrency.UZS else product.price_usd
#             if original_price is None or original_price < 0: raise serializers.ValidationError(
#                 f"'{product.name}' uchun ({currency}) asl narx noto'g'ri.")
#             if final_price_for_item < 0: raise serializers.ValidationError(
#                 f"'{product.name}' uchun yakuniy narx manfiy bo'lishi mumkin emas.")
#             calculated_original_total += original_price * quantity
#             calculated_final_total += final_price_for_item * quantity
#         if calculated_final_total <= 0 and payment_type != Sale.PaymentType.INSTALLMENT: raise serializers.ValidationError(
#             "Sotuvning yakuniy summasi 0 dan katta bo'lishi kerak.")
#
#         self.context['calculated_original_total_in_currency'] = calculated_original_total
#         self.context['calculated_final_total_in_currency'] = calculated_final_total
#
#         if payment_type == Sale.PaymentType.INSTALLMENT:
#             term_months = data.get('installment_term_months');
#             down_payment = data.get('installment_down_payment', Decimal(0))
#             initial_amount_for_installment = calculated_final_total
#             if not term_months or term_months < 1: raise serializers.ValidationError(
#                 {"installment_term_months": ["Nasiya muddati 1 oydan kam bo'lmasligi kerak."]})
#             if down_payment > initial_amount_for_installment: raise serializers.ValidationError({
#                                                                                                     "installment_down_payment": [
#                                                                                                         f"Boshlang'ich to'lov ({down_payment}) nasiya summasidan ({initial_amount_for_installment}) oshmasligi kerak."]})
#             data['installment_initial_amount'] = initial_amount_for_installment
#         return data
#
#     @transaction.atomic
#     def create(self, validated_data):
#         from installments.serializers import InstallmentPlanCreateSerializer  # Import shu yerda
#
#         request = self.context.get('request')
#         user = validated_data.pop('user', request.user if request else None)
#         items_data = validated_data.pop('items')
#         kassa = validated_data.pop('kassa_id')
#         payment_type = validated_data.pop('payment_type')
#         sale_currency_code = validated_data.pop('currency')  # Nomini o'zgartirdim
#         customer_id_obj = validated_data.pop('customer_id', None)
#         new_customer_data = validated_data.pop('new_customer', None)
#         installment_down_payment = validated_data.pop('installment_down_payment', Decimal(0))
#         installment_interest_rate = validated_data.pop('installment_interest_rate', Decimal(0))
#         installment_term_months = validated_data.pop('installment_term_months', None)
#         installment_initial_amount_for_plan = validated_data.pop('installment_initial_amount',
#                                                                  self.context.get('calculated_final_total_in_currency'))
#
#         customer_for_sale = customer_id_obj
#         if not customer_for_sale and new_customer_data:
#             phone = new_customer_data.get('phone_number')
#             if not phone: raise ValidationError(
#                 {"new_customer.phone_number": "Yangi mijoz uchun telefon raqami majburiy."})
#             customer_for_sale, _ = Customer.objects.get_or_create(phone_number=phone, defaults={
#                 'full_name': new_customer_data.get('full_name', f"Mijoz {phone}"),
#                 'address': new_customer_data.get('address')})
#
#         original_total = self.context.get('calculated_original_total_in_currency')
#         final_total_for_sale = self.context.get('calculated_final_total_in_currency')
#         if original_total is None or final_total_for_sale is None: raise ValidationError(
#             "Sotuv summalari validatsiyada hisoblanmagan.")
#
#         amount_to_register_as_paid = final_total_for_sale
#         if payment_type == Sale.PaymentType.INSTALLMENT:
#             amount_to_register_as_paid = installment_down_payment
#
#         sale = Sale.objects.create(
#             seller=user, customer=customer_for_sale, kassa=kassa, currency=sale_currency_code,
#             original_total_amount_currency=original_total,
#             final_amount_currency=final_total_for_sale,
#             amount_actually_paid_at_sale=amount_to_register_as_paid,
#             payment_type=payment_type, status=Sale.SaleStatus.COMPLETED
#         )
#
#         for item_data_loop in items_data:
#             product = item_data_loop['product_id'];
#             quantity = item_data_loop['quantity']
#             final_price_for_item_in_sale_currency = item_data_loop['price']
#
#             price_usd_to_save, price_uzs_to_save = None, None
#             original_price_usd_item, original_price_uzs_item = product.price_usd, product.price_uzs  # Asl narxlarni olish
#
#             if sale_currency_code == Sale.SaleCurrency.UZS:
#                 price_uzs_to_save = final_price_for_item_in_sale_currency
#             elif sale_currency_code == Sale.SaleCurrency.USD:
#                 price_usd_to_save = final_price_for_item_in_sale_currency
#
#             SaleItem.objects.create(
#                 sale=sale, product=product, quantity=quantity,
#                 price_at_sale_usd=price_usd_to_save, price_at_sale_uzs=price_uzs_to_save,
#                 original_price_at_sale_usd_item=original_price_usd_item,  # Saqlash
#                 original_price_at_sale_uzs_item=original_price_uzs_item  # Saqlash
#             )
#             try:
#                 stock = ProductStock.objects.select_for_update().get(product=product, kassa=kassa)
#                 if stock.quantity < quantity: raise ValidationError(f"{product.name} uchun qoldiq yetarli emas.")
#                 stock.quantity -= quantity;
#                 stock.save(update_fields=['quantity'])
#             except ProductStock.DoesNotExist:
#                 raise ValidationError(f"{product.name} uchun {kassa.name} da ombor yozuvi topilmadi.")
#             InventoryOperation.objects.create(product=product, kassa=kassa, user=user, quantity=-quantity,
#                                               operation_type=InventoryOperation.OperationType.SALE,
#                                               comment=f"Sotuv #{sale.id}")
#
#         # O'ZGARTIRILDI: KassaTransaction yaratishda valyutani hisobga olish
#         if amount_to_register_as_paid > 0:
#             kassa_trans_type = KassaTransaction.TransactionType.SALE
#             if payment_type == Sale.PaymentType.INSTALLMENT:
#                 kassa_trans_type = KassaTransaction.TransactionType.INSTALLMENT_PAYMENT
#
#             KassaTransaction.objects.create(
#                 kassa=kassa,
#                 currency=sale_currency_code,  # Sotuv valyutasi
#                 amount=amount_to_register_as_paid,  # Sotuv valyutasidagi summa
#                 transaction_type=kassa_trans_type,
#                 user=user,
#                 comment=f"Sotuv #{sale.id} ({sale_currency_code})",
#                 related_sale=sale
#             )
#
#         if payment_type == Sale.PaymentType.INSTALLMENT:
#             if installment_initial_amount_for_plan is None or installment_initial_amount_for_plan <= 0: raise ValidationError(
#                 "Nasiya uchun asosiy summa 0 dan katta bo'lishi shart.")
#             if installment_term_months is None: raise ValidationError("Nasiya muddati kiritilishi shart.")
#             installment_plan_data = {
#                 'sale': sale.pk, 'customer': customer_for_sale.pk, 'currency': sale_currency_code,
#                 'initial_amount': installment_initial_amount_for_plan,
#                 'down_payment': installment_down_payment,
#                 'interest_rate': installment_interest_rate,
#                 'term_months': installment_term_months,
#             }
#             plan_serializer = InstallmentPlanCreateSerializer(data=installment_plan_data, context=self.context)
#             if plan_serializer.is_valid(raise_exception=True): plan_serializer.save()
#         return sale


class SaleReturnItemInputSerializer(serializers.Serializer):
    # ... (o'zgarishsiz)
    sale_item_id = serializers.PrimaryKeyRelatedField(queryset=SaleItem.objects.all(), label="Sotuv Elementi ID")
    quantity = serializers.IntegerField(min_value=1, label="Qaytariladigan miqdor")


class SaleReturnSerializer(serializers.Serializer):
    # ... (refund_method o'zgarishsiz)
    items_to_return = SaleReturnItemInputSerializer(many=True, required=True, min_length=1,
                                                    label="Qaytariladigan mahsulotlar")
    reason = serializers.CharField(required=False, allow_blank=True, label="Qaytarish sababi")
    refund_method = serializers.ChoiceField(
        choices=[('Naqd', 'Naqd Pul'), ('Karta', 'Kartaga'), ('None', "Pul qaytarilmaydi")], default='Naqd',
        label="Pulni Qaytarish Usuli")

    def validate_items_to_return(self, items):
        # ... (validate logikasi o'zgarishsiz, self.context ga sale_instance yozadi)
        if not items: raise serializers.ValidationError("Qaytarish uchun kamida bitta mahsulot tanlang.")
        sale_id = None;
        sale_items_map = {}
        for item_data in items:
            sale_item_id = item_data['sale_item_id'].id;
            quantity_to_return = item_data['quantity']
            try:
                sale_item = SaleItem.objects.select_related('sale__kassa', 'product').get(id=sale_item_id);
                sale_items_map[sale_item_id] = sale_item
            except SaleItem.DoesNotExist:
                raise serializers.ValidationError({
                                                      f"items_to_return[{items.index(item_data)}].sale_item_id": f"ID={sale_item_id} bilan sotuv elementi topilmadi."})
            current_sale_id = sale_item.sale_id
            if sale_id is None:
                sale_id = current_sale_id; sale = sale_item.sale; self.context['sale_instance'] = sale;
            elif current_sale_id != sale_id:
                raise serializers.ValidationError(
                    "Barcha qaytariladigan mahsulotlar bir xil sotuvga tegishli bo'lishi kerak.")
            if not sale.can_be_returned: raise serializers.ValidationError(
                f"Ushbu sotuv '{sale.get_status_display()}' holatida, qaytarib bo'lmaydi.")
            if quantity_to_return > sale_item.quantity_available_to_return: raise serializers.ValidationError(
                f"'{sale_item.product.name}' uchun faqat {sale_item.quantity_available_to_return} dona qaytarish mumkin (so'ralgan: {quantity_to_return}).")
        self.context['sale_items_to_process'] = sale_items_map
        return items

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data['items_to_return']
        reason = validated_data.get('reason')
        refund_method = validated_data['refund_method']
        user = validated_data['user']
        sale = self.context['sale_instance']  # Asl sotuv
        sale_items_map = self.context['sale_items_to_process']
        kassa = sale.kassa

        # O'ZGARTIRILDI: Qaytariladigan summa va valyutani hisoblash
        total_returned_amount_in_sale_currency = Decimal(0)
        for item_data in items_data:  # Har bir qaytarilayotgan element uchun
            sale_item = sale_items_map[item_data['sale_item_id'].id]
            quantity_returned_for_item = item_data['quantity']
            price_at_sale_for_item = sale_item.price_at_sale_uzs if sale.currency == Sale.SaleCurrency.UZS else sale_item.price_at_sale_usd
            if price_at_sale_for_item is None:  # Xatolikni oldini olish
                price_at_sale_for_item = Decimal(0)
            total_returned_amount_in_sale_currency += price_at_sale_for_item * quantity_returned_for_item

        sale_return_obj = SaleReturn.objects.create(
            original_sale=sale, reason=reason, returned_by=user,
            returned_amount_currency_value=total_returned_amount_in_sale_currency,  # O'ZGARTIRILDI
            currency_of_return=sale.currency  # O'ZGARTIRILDI: Sotuvning asl valyutasi
        )

        inventory_ops_to_create = [];
        sale_items_to_update = [];
        product_stock_updates = {}
        for item_data in items_data:
            sale_item_id = item_data['sale_item_id'].id;
            quantity_returned = item_data['quantity']
            sale_item = sale_items_map[sale_item_id]
            SaleReturnItem.objects.create(sale_return=sale_return_obj, sale_item=sale_item,
                                          quantity_returned=quantity_returned)
            sale_item.quantity_returned += quantity_returned;
            sale_items_to_update.append(sale_item)
            product_id = sale_item.product_id
            product_stock_updates[product_id] = product_stock_updates.get(product_id, 0) + quantity_returned
            inventory_ops_to_create.append(
                InventoryOperation(product=sale_item.product, kassa=kassa, user=user, quantity=quantity_returned,
                                   operation_type=InventoryOperation.OperationType.RETURN,
                                   comment=f"Sotuv #{sale.id} qaytarish #{sale_return_obj.id}"))

        stocks_to_update = ProductStock.objects.select_for_update().filter(product_id__in=product_stock_updates.keys(),
                                                                           kassa=kassa)
        for stock in stocks_to_update: stock.quantity += product_stock_updates[stock.product_id]
        ProductStock.objects.bulk_update(stocks_to_update, ['quantity'])
        InventoryOperation.objects.bulk_create(inventory_ops_to_create)
        SaleItem.objects.bulk_update(sale_items_to_update, ['quantity_returned'])

        all_items = sale.items.all()
        if all(si.quantity_available_to_return == 0 for si in all_items):
            sale.status = Sale.SaleStatus.RETURNED
        else:
            sale.status = Sale.SaleStatus.PARTIALLY_RETURNED
        sale.save(update_fields=['status'])

        if sale.payment_type == Sale.PaymentType.INSTALLMENT:
            try:
                plan = sale.installmentplan  # Property orqali
                plan.adjust_for_return(total_returned_amount_in_sale_currency)  # Sotuv valyutasidagi summa bilan
                plan.save()
            except InstallmentPlan.DoesNotExist:
                pass
            except Exception as e:
                print(f"Error adjusting installment for return {sale.id}: {e}")

        # O'ZGARTIRILDI: KassaTransaction yaratishda qaytarish valyutasini hisobga olish
        if refund_method == 'Naqd' and total_returned_amount_in_sale_currency > 0:
            KassaTransaction.objects.create(
                kassa=kassa,
                currency=sale.currency,  # Qaytarish sotuvning asl valyutasida
                amount=total_returned_amount_in_sale_currency,  # Sotuv valyutasidagi summa
                transaction_type=KassaTransaction.TransactionType.RETURN_REFUND,
                user=user,
                comment=f"Sotuv #{sale.id} ({sale.currency}) uchun qaytarish #{sale_return_obj.id}",
                related_return=sale_return_obj
            )
        return SaleDetailSerializer(instance=sale, context=self.context).data


class SaleReturnItemDetailSerializer(serializers.ModelSerializer):
    # ... (o'zgarishsiz)
    product_name = serializers.CharField(source='sale_item.product.name', read_only=True)
    price_at_sale_uzs = serializers.DecimalField(source='sale_item.price_at_sale_uzs', max_digits=15, decimal_places=2,
                                                 read_only=True, allow_null=True)
    price_at_sale_usd = serializers.DecimalField(source='sale_item.price_at_sale_usd', max_digits=10, decimal_places=2,
                                                 read_only=True, allow_null=True)

    class Meta: model = SaleReturnItem; fields = ['id', 'product_name', 'quantity_returned', 'price_at_sale_uzs',
                                                  'price_at_sale_usd']  # USD ham qo'shildi


class SaleReturnDetailSerializer(serializers.ModelSerializer):
    original_sale_id = serializers.IntegerField(source='original_sale.id', read_only=True)
    original_sale_currency = serializers.CharField(source='original_sale.currency', read_only=True)  # Sotuv valyutasi
    returned_by_username = serializers.CharField(source='returned_by.username', read_only=True, allow_null=True)
    items = SaleReturnItemDetailSerializer(many=True, read_only=True)

    class Meta: model = SaleReturn; fields = ['id', 'original_sale_id', 'original_sale_currency', 'reason',
                                              'returned_by_username', 'created_at', 'returned_amount_currency_value',
                                              'currency_of_return', 'items']  # Valyutalar qo'shildi


class PosProductSerializer(serializers.ModelSerializer):
    # ... (o'zgarishsiz)
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True);
    price_uzs = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True, allow_null=True);
    quantity_in_stock = serializers.IntegerField(read_only=True, default=0)

    class Meta: model = Product; fields = ['id', 'name', 'barcode', 'category_name', 'price_uzs', 'price_usd',
                                           'quantity_in_stock']; read_only_fields = fields


class KassaTransactionSerializer(serializers.ModelSerializer):
    kassa_name = serializers.CharField(source='kassa.name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True, allow_null=True)
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    related_sale_id = serializers.PrimaryKeyRelatedField(source='related_sale', read_only=True, allow_null=True)
    related_payment_id = serializers.PrimaryKeyRelatedField(source='related_installment_payment', read_only=True,
                                                            allow_null=True)
    related_return_id = serializers.PrimaryKeyRelatedField(source='related_return', read_only=True, allow_null=True)

    class Meta:
        model = KassaTransaction
        fields = [
            'id', 'kassa', 'kassa_name',
            'currency',  # YANGI QO'SHILDI
            'amount', 'transaction_type', 'transaction_type_display',
            'user', 'user_username', 'comment', 'timestamp',
            'related_sale_id', 'related_payment_id', 'related_return_id'
        ]
        read_only_fields = fields


class BaseCashOperationSerializer(serializers.Serializer):
    kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.filter(is_active=True), label="Kassa")
    # YANGI QO'SHILDI: Amaliyot valyutasi
    currency = serializers.ChoiceField(choices=Sale.SaleCurrency.choices, default=Sale.SaleCurrency.UZS,
                                       label="Valyuta")
    amount = serializers.DecimalField(max_digits=17, decimal_places=2, min_value=Decimal('0.01'), label="Summa")
    comment = serializers.CharField(required=False, allow_blank=True, label="Izoh")

    def validate_kassa_id(self, kassa): return kassa


class CashInSerializer(BaseCashOperationSerializer):
    def save(self, **kwargs):
        validated_data = {**self.validated_data, **kwargs}
        transaction = KassaTransaction.objects.create(
            kassa=validated_data['kassa_id'],
            currency=validated_data['currency'],  # YANGI
            amount=validated_data['amount'],
            transaction_type=KassaTransaction.TransactionType.CASH_IN,
            user=validated_data['user'],
            comment=validated_data.get('comment')
        )
        return transaction


class CashOutSerializer(BaseCashOperationSerializer):
    def save(self, **kwargs):
        validated_data = {**self.validated_data, **kwargs}
        # Balansni tekshirish kerak bo'lsa, reports.services dan get_kassa_balance_currency ni chaqirish
        # current_balance = get_kassa_balance_currency(validated_data['kassa_id'].id, validated_data['currency'])
        # if current_balance is None or validated_data['amount'] > current_balance:
        #     raise serializers.ValidationError(f"Kassada yetarli {validated_data['currency']} mablag' yo'q.")
        transaction = KassaTransaction.objects.create(
            kassa=validated_data['kassa_id'],
            currency=validated_data['currency'],  # YANGI
            amount=validated_data['amount'],
            transaction_type=KassaTransaction.TransactionType.CASH_OUT,
            user=validated_data['user'],
            comment=validated_data.get('comment')
        )
        return transaction


# YANGI: Valyuta ayirboshlash uchun Serializer
class CurrencyExchangeSerializer(serializers.Serializer):
    kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.filter(is_active=True), label="Kassa")
    from_currency = serializers.ChoiceField(choices=Sale.SaleCurrency.choices, label="Qaysi valyutadan")
    to_currency = serializers.ChoiceField(choices=Sale.SaleCurrency.choices, label="Qaysi valyutaga")
    amount_to_sell = serializers.DecimalField(max_digits=17, decimal_places=2, min_value=Decimal('0.01'),
                                              label="Sotiladigan summa")
    exchange_rate = serializers.DecimalField(max_digits=17, decimal_places=4, min_value=Decimal('0.0001'),
                                             label="Ayirboshlash kursi", required=False,
                                             help_text="Agar bo'sh bo'lsa, sozlamalardan olinadi (USD->UZS)")
    # amount_to_receive = serializers.DecimalField(max_digits=17, decimal_places=2, min_value=Decimal('0.01'), label="Olinadigan summa", required=False, help_text="Agar bo'sh bo'lsa, kurs bo'yicha hisoblanadi")
    comment = serializers.CharField(required=False, allow_blank=True, label="Izoh")

    def validate(self, data):
        if data['from_currency'] == data['to_currency']:
            raise serializers.ValidationError({"to_currency": "Valyutalar bir xil bo'lishi mumkin emas."})

        # Kassa balansini tekshirish (sotiladigan valyuta uchun)
        # balance = get_kassa_balance_currency(data['kassa_id'].id, data['from_currency'])
        # if balance is None or data['amount_to_sell'] > balance:
        #     raise serializers.ValidationError({"amount_to_sell": f"Kassada sotish uchun yetarli {data['from_currency']} yo'q."})

        # Kurs va olinadigan summani hisoblash/tekshirish logikasi
        # ... (bu qismni batafsilroq yozish kerak, agar amount_to_receive ham kiritilsa)
        return data

    @transaction.atomic
    def save(self, **kwargs):
        from settings_app.models import CurrencyRate  # Kursni olish uchun

        kassa = self.validated_data['kassa_id']
        from_currency = self.validated_data['from_currency']
        to_currency = self.validated_data['to_currency']
        amount_to_sell = self.validated_data['amount_to_sell']
        exchange_rate_input = self.validated_data.get('exchange_rate')
        comment = self.validated_data.get('comment')
        user = kwargs.get('user')

        calculated_amount_to_receive = Decimal(0)
        actual_exchange_rate = None

        if from_currency == Sale.SaleCurrency.USD and to_currency == Sale.SaleCurrency.UZS:  # USD sotib UZS olish
            actual_exchange_rate = exchange_rate_input or CurrencyRate.load().usd_to_uzs_rate
            calculated_amount_to_receive = amount_to_sell * actual_exchange_rate
            sell_op_type = KassaTransaction.TransactionType.EXCHANGE_SELL_CURRENCY  # USD chiqim
            buy_op_type = KassaTransaction.TransactionType.EXCHANGE_BUY_CURRENCY  # UZS kirim
        elif from_currency == Sale.SaleCurrency.UZS and to_currency == Sale.SaleCurrency.USD:  # UZS sotib USD olish
            rate_usd_to_uzs = exchange_rate_input or CurrencyRate.load().usd_to_uzs_rate
            if rate_usd_to_uzs == 0: raise serializers.ValidationError("USD->UZS kursi 0 bo'lishi mumkin emas.")
            actual_exchange_rate = Decimal(1) / rate_usd_to_uzs  # UZS->USD kursi
            calculated_amount_to_receive = amount_to_sell * actual_exchange_rate  # Yoki amount_to_sell / rate_usd_to_uzs
            sell_op_type = KassaTransaction.TransactionType.EXCHANGE_SELL_CURRENCY  # UZS chiqim
            buy_op_type = KassaTransaction.TransactionType.EXCHANGE_BUY_CURRENCY  # USD kirim
        else:
            raise serializers.ValidationError("Hozircha faqat USD va UZS orasida ayirboshlash mumkin.")

        calculated_amount_to_receive = calculated_amount_to_receive.quantize(Decimal('0.01'))

        # Chiqim operatsiyasi (sotilayotgan valyuta uchun)
        out_transaction = KassaTransaction.objects.create(
            kassa=kassa, currency=from_currency, amount=amount_to_sell,
            transaction_type=sell_op_type, user=user,
            comment=f"{comment or ''} ({amount_to_sell} {from_currency} -> {calculated_amount_to_receive} {to_currency} @ {actual_exchange_rate:.4f})"
        )
        # Kirim operatsiyasi (olinayotgan valyuta uchun)
        in_transaction = KassaTransaction.objects.create(
            kassa=kassa, currency=to_currency, amount=calculated_amount_to_receive,
            transaction_type=buy_op_type, user=user,
            comment=f"{comment or ''} ({amount_to_sell} {from_currency} -> {calculated_amount_to_receive} {to_currency} @ {actual_exchange_rate:.4f})"
        )
        return {"sold": KassaTransactionSerializer(out_transaction).data,
                "received": KassaTransactionSerializer(in_transaction).data}