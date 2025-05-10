# sales/serializers.py
from decimal import Decimal

from rest_framework import serializers
from django.db import transaction
from rest_framework.exceptions import PermissionDenied


# SaleStatus ni bu importdan olib tashlaymiz:
from .models import Customer, Sale, SaleItem, KassaTransaction
from .models import Customer, Sale, SaleItem, SaleReturn, SaleReturnItem
from products.models import Product, Kassa
from products.serializers import ProductSerializer as ProductListSerializer, ProductSerializer
from products.serializers import KassaSerializer
from users.serializers import UserSerializer
from inventory.models import ProductStock, InventoryOperation
from django.utils import timezone
from rest_framework.validators import UniqueValidator
# Installments importlarini fayl boshidan olib tashlaymiz
# from installments.serializers import InstallmentPlanCreateSerializer # <<< Olib tashlandi
# from installments.models import InstallmentPlan                   # <<< Olib tashlandi

class CustomerSerializer(serializers.ModelSerializer):
    """Mijozlar uchun Serializer (Do'kon ichida telefon raqam unikalligini tekshiradi)"""
    class Meta:
        model = Customer
        fields = ['id', 'full_name', 'phone_number', 'email', 'address', 'created_at']
        # ---- Tekshiring ----
        read_only_fields = ('created_at',) # KORTEJ YOKI LIST (vergul muhim)
        # Yoki: read_only_fields = ['created_at']

    # def validate_phone_number(self, value):
    #     request = self.context.get('request')
    #     user = request.user if request else None
    #     instance = self.instance


class SaleItemSerializer(serializers.ModelSerializer):
    """Sotuv elementlarini ko'rsatish uchun"""
    product = ProductSerializer(read_only=True) # ProductListSerializer o'rniga to'liq ProductSerializer
    item_total_usd = serializers.ReadOnlyField()
    item_total_uzs = serializers.ReadOnlyField()
    quantity_available_to_return = serializers.ReadOnlyField()

    class Meta:
        model = SaleItem
        fields = [
            'id', 'product', 'quantity', 'price_at_sale_usd', 'price_at_sale_uzs',
            'item_total_usd', 'item_total_uzs', 'quantity_returned', 'quantity_available_to_return'
        ]


class SaleListSerializer(serializers.ModelSerializer):
    """Sotuvlar ro'yxatini ko'rsatish uchun (kamroq ma'lumot)"""
    seller_username = serializers.CharField(source='seller.username', read_only=True, default=None)
    customer_name = serializers.CharField(source='customer.full_name', read_only=True, default=None)
    kassa_name = serializers.CharField(source='kassa.name', read_only=True)
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    # SerializerMethodField o'rniga oddiy IntegerField
    items_count = serializers.IntegerField(read_only=True, default=0)  # default qo'shildi
    products_preview = serializers.SerializerMethodField()  # Bu qolishi mumkin

    class Meta:
        model = Sale
        fields = [
            'id', 'seller_username', 'customer_name', 'kassa_name',
            'total_amount_uzs', 'total_amount_usd',
            'payment_type', 'payment_type_display', 'status', 'status_display', 'created_at',
            'items_count', 'products_preview'
        ]

    # get_items_count metodi olib tashlandi
    # def get_items_count(self, obj): ...

    def get_products_preview(self, obj):
        # Bu yerda obj.items ga murojaat qilish xavfsizroq bo'lishi mumkin,
        # lekin baribir ehtiyot bo'lish kerak. Annotate qilish yaxshiroq.
        # Yoki Sale obyektiga count ni property sifatida qo'shish mumkin.
        # Hozircha shunday qoldiramiz, lekin annotate afzalroq.
        try:
            # Agar items prefetch qilingan bo'lsa bu ishlashi kerak
            items = obj.items.all()
            if not items: return "Yo'q"
            limit = 2
            names = [item.product.name for item in items[:limit]]
            preview = ", ".join(names)
            if len(items) > limit: preview += ", ..."
            return preview
        except:  # Har ehtimolga qarshi
            return "-"

class SaleDetailSerializer(SaleListSerializer):
    """Bitta sotuvning batafsil ma'lumotlari"""
    items = SaleItemSerializer(many=True, read_only=True)
    seller = UserSerializer(read_only=True)
    customer = CustomerSerializer(read_only=True)
    kassa = KassaSerializer(read_only=True)
    installment_plan_id = serializers.IntegerField(source='installmentplan.id', read_only=True, default=None)

    class Meta(SaleListSerializer.Meta):
        fields = [f for f in SaleListSerializer.Meta.fields if f != 'products_preview'] + [
             'items', 'seller', 'customer', 'kassa',
             'amount_paid_uzs', 'installment_plan_id'
         ] # products_preview ni olib tashladik detalda


# --- Yangi Sotuv Uchun INPUT Serializerlar ---

class SaleItemInputSerializer(serializers.Serializer):
    """Sotuv uchun kiruvchi mahsulot ma'lumoti"""
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
        label="Mahsulot ID"
    )
    quantity = serializers.IntegerField(min_value=1, label="Miqdor")


class SaleCreateSerializer(serializers.Serializer):
    items = SaleItemInputSerializer(many=True, required=True, min_length=1, label="Mahsulotlar")
    payment_type = serializers.ChoiceField(choices=Sale.PaymentType.choices, label="To'lov turi")
    kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.all(), label="Kassa")
    customer_id = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), required=False, allow_null=True, label="Mijoz")
    amount_paid_uzs_initial = serializers.DecimalField(
        max_digits=17, decimal_places=2, required=False, default=Decimal(0), min_value=Decimal(0),
        label="Boshlang'ich to'lov (Nasiya uchun)"
    )

    def validate_kassa_id(self, kassa):
        # Bu yerda store tekshiruvi yo'q, chunki bitta do'kon uchun ishlayapmiz
        if not kassa.is_active:
             raise serializers.ValidationError("Tanlangan kassa aktiv emas.")
        return kassa

    def validate_customer_id(self, customer):
        # Bu yerda ham store tekshiruvi yo'q
        return customer

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("Sotuv uchun kamida bitta mahsulot tanlanishi kerak.")

        kassa_from_initial_data = self.initial_data.get('kassa_id')  # Bu ID (string yoki int) bo'lishi mumkin
        kassa_obj = None

        if not kassa_from_initial_data:
            raise serializers.ValidationError({"kassa_id": "Kassa tanlanmagan (validate_items)."})

        try:
            # kassa_id ni Kassa obyektiga aylantirish
            kassa_obj = Kassa.objects.get(pk=int(kassa_from_initial_data))
        except (Kassa.DoesNotExist, ValueError, TypeError):
            raise serializers.ValidationError({"kassa_id": "Noto'g'ri kassa ID si yoki kassa topilmadi."})

        if not kassa_obj.is_active:  # Kassaning aktivligini tekshirish
            raise serializers.ValidationError({"kassa_id": "Tanlangan kassa aktiv emas."})

        product_quantities = {}  # product_id -> quantity xaritasi
        product_ids_to_check = []

        for item_data in items:
            product = item_data['product_id']  # Bu Product obyekti
            # Store tekshiruvi olib tashlangan (chunki bitta do'kon uchun)
            product_ids_to_check.append(product.id)
            product_quantities[product.id] = item_data['quantity']

        # ProductStock yozuvlarini olish
        # Bu yerda in_bulk o'rniga oddiy filter va loop ishlatib ko'ramiz debugging uchun
        # stocks_dict = ProductStock.objects.filter(
        #     product_id__in=product_ids_to_check, kassa=kassa_obj
        # ).in_bulk(field_name='product_id')

        # Muqobil yondashuv (in_bulk siz, agar yuqoridagi xato davom etsa):
        stocks_qs = ProductStock.objects.filter(
            product_id__in=product_ids_to_check, kassa=kassa_obj
        )

        # Har bir mahsulot uchun qoldiqni tekshirish
        for product_id in product_ids_to_check:
            quantity_to_sell = product_quantities[product_id]

            # stocks_qs dan kerakli stockni topish
            stock = next((s for s in stocks_qs if s.product_id == product_id), None)

            if stock is None or stock.quantity < quantity_to_sell:
                available_qty = stock.quantity if stock else 0
                try:
                    product_name = Product.objects.get(pk=product_id).name
                except Product.DoesNotExist:
                    product_name = f"ID={product_id}"
                raise serializers.ValidationError(
                    f"'{product_name}' uchun {kassa_obj.name} kassasida yetarli qoldiq yo'q "
                    f"(Mavjud: {available_qty}, So'ralgan: {quantity_to_sell})."
                )
        return items

    def validate(self, data):
        payment_type = data['payment_type']
        customer = data.get('customer_id')
        amount_paid_initial = data.get('amount_paid_uzs_initial', Decimal(0))

        if payment_type == Sale.PaymentType.INSTALLMENT:
            if not customer:
                raise serializers.ValidationError({"customer_id": "Nasiya savdo uchun mijoz tanlanishi shart."})
        elif amount_paid_initial != Decimal(0):
            raise serializers.ValidationError({"amount_paid_uzs_initial": "Boshlang'ich to'lov faqat Nasiya savdo uchun kiritiladi."})
        return data

    # --- Mana shu create metodi ---
    @transaction.atomic
    def create(self, validated_data):
        # --- Kerakli importlar (agar global import qilinmagan bo'lsa) ---
        from installments.serializers import InstallmentPlanCreateSerializer # Nasiya uchun

        # --- Contextdan foydalanuvchini olish ---
        request = self.context.get('request')
        user = request.user if request else None # Yoki kwargs dan olish (agar perform_create orqali berilsa)
        if 'user' in validated_data: # Agar viewdan uzatilgan bo'lsa (perform_create)
            user = validated_data.pop('user')

        if not user or not user.is_authenticated:
            # Bu holat odatda permissionlar bilan ushlanadi, lekin himoya uchun
            raise serializers.ValidationError("Sotuvni amalga oshirish uchun foydalanuvchi autentifikatsiyadan o'tgan bo'lishi kerak.")

        # --- Validated_data dan ma'lumotlarni olish ---
        items_data = validated_data.pop('items')
        kassa = validated_data.pop('kassa_id') # Bu Kassa obyekti
        payment_type = validated_data.pop('payment_type')
        customer = validated_data.pop('customer_id', None) # Bu Customer obyekti yoki None
        amount_paid_initial = validated_data.pop('amount_paid_uzs_initial', Decimal(0))

        # --- Qoldiqlarni qayta tekshirish (select_for_update bilan) ---
        product_ids = [item['product_id'].id for item in items_data]
        stocks_qs = ProductStock.objects.select_for_update().filter(
            product_id__in=product_ids, kassa=kassa
        )
        stocks = {stock.product_id: stock for stock in stocks_qs} # dict ga o'tkazish

        total_usd = Decimal(0)
        total_uzs = Decimal(0)
        sale_items_to_create = []
        inventory_operations_to_create = []
        stocks_to_update_list = [] # bulk_update uchun list

        for item_data in items_data:
            product = item_data['product_id']
            quantity = item_data['quantity']
            stock = stocks.get(product.id) # dict dan olish

            if stock is None or stock.quantity < quantity:
                 current_stock = ProductStock.objects.filter(product=product, kassa=kassa).first() # Qayta so'rov
                 if current_stock is None or current_stock.quantity < quantity:
                      raise serializers.ValidationError(
                           f"'{product.name}' uchun qoldiq yetarli emas (qayta tekshirishda aniqlandi). "
                           f"Mavjud: {current_stock.quantity if current_stock else 0}, So'ralgan: {quantity}."
                      )
                 stock = current_stock
                 stocks[product.id] = stock # Agar dict da bo'lmasa qo'shish

            # Mahsulot narxlarini olish (USD yoki UZS, ikkalasidan biri bo'lishi kerak)
            item_price_usd = product.price_usd if product.price_usd is not None else Decimal(0)
            item_price_uzs = product.price_uzs if product.price_uzs is not None else Decimal(0)

            # Talab: Ikkalasidan biri kiritilishi shart (bu ProductSerializerda tekshiriladi)
            # Bu yerda himoya: agar ikkalasi ham 0 bo'lsa, qaysidir valyutada narx yo'q
            # Lekin sotuvda UZS summani hisoblaymiz (yoki USD, kelishuvga qarab)
            # Hozircha, agar UZS narx 0 bo'lsa, lekin USD narx bo'lsa, total_uzs ga qo'shmaymiz
            # Yoki doim UZS da hisoblash kerakmi? (savolda kurs kerak emas deyilgan)
            # Eng yaxshisi, agar ikkala narx ham berilgan bo'lsa, UZS ni ustun qo'yish yoki frontend tanlashi
            # Hozirgi talab: ikkalasidan biri. Sotuvda qaysi birini asosiy deb olamiz?

            # Variant: Agar UZS narx bo'lsa, uni ishlatamiz. Bo'lmasa USD ni (lekin uni UZS ga o'tkazmaymiz)
            # Bu total_amount_uzs va total_amount_usd ni alohida saqlashni talab qiladi.
            if item_price_uzs > 0:
                total_uzs += item_price_uzs * quantity
            elif item_price_usd > 0: # Agar UZS yo'q, lekin USD bor bo'lsa
                 total_usd += item_price_usd * quantity
                 # total_uzs ga nima qilamiz? Agar kurs yo'q bo'lsa, total_uzs faqat UZS narxlardan yig'iladi
            else: # Ikkala narx ham 0 yoki None (bu ProductSerializerda ushlanishi kerak)
                 raise serializers.ValidationError(f"'{product.name}' mahsuloti uchun sotish narxi topilmadi.")


            sale_items_to_create.append(SaleItem(
                product=product, quantity=quantity,
                price_at_sale_usd=item_price_usd, # Sotuv paytidagi USD narx
                price_at_sale_uzs=item_price_uzs  # Sotuv paytidagi UZS narx
                # sale keyinroq bog'lanadi
            ))
            inventory_operations_to_create.append(InventoryOperation(
                product=product, kassa=kassa, user=user, quantity=-quantity,
                operation_type=InventoryOperation.OperationType.SALE
                # comment keyinroq bog'lanadi
            ))
            stock.quantity -= quantity
            stocks_to_update_list.append(stock)

        # --- Nasiya uchun boshlang'ich to'lovni tekshirish ---
        # total_amount_uzs ni asosiy summa deb olamiz (agar UZS da narxlar bo'lsa)
        # Agar faqat USD narxlar bo'lsa, qanday yo'l tutamiz?
        # Hozircha total_uzs ni asosiy deb hisoblaymiz.
        if payment_type == Sale.PaymentType.INSTALLMENT and amount_paid_initial > total_uzs:
            # Agar total_uzs 0 bo'lsa (faqat USD narxlar), bu xato beradi.
            # Bu logikani qayta ko'rib chiqish kerak, agar faqat USD da sotilsa.
            if total_uzs > 0 : # Faqat UZS da summa bo'lsa tekshiramiz
                 raise serializers.ValidationError({
                     "amount_paid_uzs_initial": f"Boshlang'ich to'lov ({amount_paid_initial}) umumiy UZS summadan ({total_uzs}) oshmasligi kerak."
                 })
            # Agar total_uzs 0 bo'lib, faqat total_usd bo'lsa, amount_paid_initial ham USD da bo'lishi kerakmi?
            # Bu talablarni aniqlashtirish kerak. Hozircha UZS ga fokus qilamiz.

        # --- Asosiy Sotuv (Sale) obyektini yaratish ---
        sale = Sale.objects.create(
            # store maydoni olib tashlangan
            seller=user,
            customer=customer,
            kassa=kassa,
            total_amount_usd=total_usd, # Hisoblangan umumiy USD
            total_amount_uzs=total_uzs, # Hisoblangan umumiy UZS
            payment_type=payment_type,
            amount_paid_uzs=(amount_paid_initial if payment_type == Sale.PaymentType.INSTALLMENT else total_uzs), # UZS da to'langan
            status=Sale.SaleStatus.COMPLETED
        )

        for sale_item in sale_items_to_create: sale_item.sale = sale
        SaleItem.objects.bulk_create(sale_items_to_create)

        for op in inventory_operations_to_create: op.comment = f"Sotuv #{sale.id}"
        InventoryOperation.objects.bulk_create(inventory_operations_to_create)

        ProductStock.objects.bulk_update(stocks_to_update_list, ['quantity'])

        # --- Kassa Tranzaksiyasini Yaratish (UZS da) ---
        transaction_amount_uzs = Decimal(0)
        transaction_type = None

        if payment_type == Sale.PaymentType.CASH:
            transaction_amount_uzs = total_uzs
            transaction_type = KassaTransaction.TransactionType.SALE
        elif payment_type == Sale.PaymentType.INSTALLMENT:
            transaction_amount_uzs = amount_paid_initial # Faqat boshlang'ich UZS to'lov
            transaction_type = KassaTransaction.TransactionType.INSTALLMENT_PAYMENT

        if transaction_amount_uzs > 0 and transaction_type:
            KassaTransaction.objects.create(
                # store maydoni olib tashlangan
                kassa=kassa,
                amount=transaction_amount_uzs,
                transaction_type=transaction_type,
                user=user,
                comment=f"Sotuv #{sale.id} ({payment_type})",
                related_sale=sale
            )

        # --- Nasiya Rejasini Yaratish (agar kerak bo'lsa, UZS da) ---
        if payment_type == Sale.PaymentType.INSTALLMENT:
            # total_due UZS da bo'lishi kerak
            if total_uzs <= 0 and total_usd > 0:
                # Agar faqat USD da sotilgan bo'lsa, nasiya qanday bo'ladi?
                # Bu holatni aniqlashtirish kerak. Hozircha xatolik beramiz.
                raise serializers.ValidationError("Faqat USD narxida nasiya savdo hozircha qo'llab-quvvatlanmaydi (kurs yo'q).")

            installment_data = {
                'sale': sale.pk,
                'customer': customer.pk,
                'total_due': total_uzs, # Nasiya UZS da
                'amount_paid': amount_paid_initial, # Boshlang'ich to'lov UZS da
            }
            installment_serializer = InstallmentPlanCreateSerializer(data=installment_data, context=self.context)
            if installment_serializer.is_valid(raise_exception=True):
                 installment_serializer.save() # store uzatilmaydi

        # --- Yaratilgan Sotuv Ma'lumotini Qaytarish ---
        sale_detail_data = SaleDetailSerializer(instance=sale, context=self.context).data
        return sale_detail_data

# --- Sotuvni Qaytarish Uchun Serializerlar ---

class SaleReturnItemInputSerializer(serializers.Serializer):
    sale_item_id = serializers.PrimaryKeyRelatedField(queryset=SaleItem.objects.all(), label="Sotuv Elementi ID")
    quantity = serializers.IntegerField(min_value=1, label="Qaytariladigan miqdor")

class SaleReturnSerializer(serializers.Serializer):
    items_to_return = SaleReturnItemInputSerializer(many=True, required=True, min_length=1, label="Qaytariladigan mahsulotlar")
    reason = serializers.CharField(required=False, allow_blank=True, label="Qaytarish sababi")

    def validate_items_to_return(self, items):
        # ... (bu metod o'zgarishsiz qoladi) ...
        if not items:
            raise serializers.ValidationError("Qaytarish uchun kamida bitta mahsulot tanlang.")
        sale_id = None
        sale_items_map = {}
        for item_data in items:
            sale_item_id = item_data['sale_item_id'].id
            quantity_to_return = item_data['quantity']
            try:
                sale_item = SaleItem.objects.select_related('sale__kassa', 'product').get(id=sale_item_id) # kassani ham olish
                sale_items_map[sale_item_id] = sale_item
            except SaleItem.DoesNotExist:
                raise serializers.ValidationError({f"items_to_return[{items.index(item_data)}].sale_item_id": f"ID={sale_item_id} bilan sotuv elementi topilmadi."})

            current_sale_id = sale_item.sale_id
            if sale_id is None:
                sale_id = current_sale_id
                sale = sale_item.sale # Sotuvni olish
                if not sale.can_be_returned: # Bu yerda tekshirish
                    raise serializers.ValidationError(f"Ushbu sotuv '{sale.get_status_display()}' holatida, qaytarib bo'lmaydi.")
                self.context['sale_instance'] = sale
            elif current_sale_id != sale_id:
                raise serializers.ValidationError("Barcha qaytariladigan mahsulotlar bir xil sotuvga tegishli bo'lishi kerak.")

            if quantity_to_return > sale_item.quantity_available_to_return:
                 raise serializers.ValidationError(
                     f"'{sale_item.product.name}' uchun faqat {sale_item.quantity_available_to_return} dona qaytarish mumkin "
                     f"(so'ralgan: {quantity_to_return})."
                 )
        self.context['sale_items_to_process'] = sale_items_map
        return items

    @transaction.atomic
    def create(self, validated_data):
        # --- Importni shu metod ichiga ko'chirdik ---
        from installments.models import InstallmentPlan
        # ------------------------------------------
        from .models import SaleReturn # SaleReturn modelini import qilish
        from .models import SaleReturnItem # SaleReturnItem modelini import qilish

        items_data = validated_data['items_to_return']
        reason = validated_data.get('reason')
        user = validated_data['user']
        sale = self.context['sale_instance']
        sale_items_map = self.context['sale_items_to_process']
        kassa = sale.kassa

        total_returned_amount_uzs = 0
        inventory_ops_to_create = []
        sale_items_to_update = []
        product_stock_updates = {}

        # --- Qaytarish operatsiyasini yaratish (avval SaleReturn kerak) ---
        sale_return_obj = SaleReturn.objects.create(
            original_sale=sale,
            reason=reason,
            returned_by=user
            # total_returned_amount_uzs keyin hisoblanadi
        )
        # ---------------------------------------------------------------

        for item_data in items_data:
            sale_item_id = item_data['sale_item_id'].id
            quantity_returned = item_data['quantity']
            sale_item = sale_items_map[sale_item_id]

            # --- SaleReturnItem yaratish ---
            SaleReturnItem.objects.create(
                sale_return=sale_return_obj, # Yaratilgan qaytarish obyektiga bog'lash
                sale_item=sale_item,
                quantity_returned=quantity_returned
            )
            # -----------------------------

            sale_item.quantity_returned += quantity_returned
            sale_items_to_update.append(sale_item)

            product_id = sale_item.product_id
            if product_id not in product_stock_updates:
                 product_stock_updates[product_id] = 0
            product_stock_updates[product_id] += quantity_returned

            inventory_ops_to_create.append(InventoryOperation(
                product=sale_item.product, kassa=kassa, user=user,
                quantity=quantity_returned, # Musbat
                operation_type=InventoryOperation.OperationType.RETURN,
                comment=f"Sotuv #{sale.id} uchun qaytarish #{sale_return_obj.id}. Sabab: {reason or '-'}",
            ))

            total_returned_amount_uzs += sale_item.price_at_sale_uzs * quantity_returned

        # --- Qaytarilgan summani SaleReturn ga yozish ---
        sale_return_obj.total_returned_amount_uzs = total_returned_amount_uzs
        sale_return_obj.save()
        # ---------------------------------------------

        stocks_to_update = ProductStock.objects.select_for_update().filter(
            product_id__in=product_stock_updates.keys(), kassa=kassa
        )
        for stock in stocks_to_update:
            stock.quantity += product_stock_updates[stock.product_id]
        ProductStock.objects.bulk_update(stocks_to_update, ['quantity'])
        InventoryOperation.objects.bulk_create(inventory_ops_to_create)
        SaleItem.objects.bulk_update(sale_items_to_update, ['quantity_returned'])

        all_items_returned = all(si.quantity_available_to_return == 0 for si in sale.items.all())
        if all_items_returned:
            sale.status = Sale.SaleStatus.RETURNED # SaleStatus ni Sale modelidan olamiz
        else:
            sale.status = Sale.SaleStatus.PARTIALLY_RETURNED # SaleStatus ni Sale modelidan olamiz
        sale.save(update_fields=['status'])

        if sale.payment_type == Sale.PaymentType.INSTALLMENT:
            try:
                plan = sale.installmentplan
                plan.adjust_for_return(total_returned_amount_uzs)
                plan.save()
                print(f"Installment plan {plan.id} adjusted for return.")
            except InstallmentPlan.DoesNotExist:
                print(f"ERROR: Installment plan not found for returned sale {sale.id}.")
            except Exception as e:
                print(f"Error adjusting installment plan for returned sale {sale.id}: {e}")

        if total_returned_amount_uzs > 0:
            KassaTransaction.objects.create(
                kassa=kassa,
                amount=total_returned_amount_uzs,
                transaction_type=KassaTransaction.TransactionType.RETURN_REFUND,
                user=user,
                comment=f"Sotuv #{sale.id} uchun qaytarish #{sale_return_obj.id}",
                related_return=sale_return_obj
            )

        updated_sale_serializer = SaleDetailSerializer(instance=sale, context=self.context)
        return updated_sale_serializer.data



# --- Qaytarish detallarini ko'rsatish uchun serializer (qo'shimcha) ---
class SaleReturnItemDetailSerializer(serializers.ModelSerializer):
     # Qaytarilgan element haqida ma'lumot
     product_name = serializers.CharField(source='sale_item.product.name', read_only=True)
     price_at_sale_uzs = serializers.DecimalField(source='sale_item.price_at_sale_uzs', max_digits=15, decimal_places=2, read_only=True)

     class Meta:
         model = SaleReturnItem
         fields = ['id', 'product_name', 'quantity_returned', 'price_at_sale_uzs']

class SaleReturnDetailSerializer(serializers.ModelSerializer):
     # To'liq qaytarish operatsiyasi haqida ma'lumot
     original_sale_id = serializers.IntegerField(source='original_sale.id', read_only=True)
     returned_by_username = serializers.CharField(source='returned_by.username', read_only=True, default=None)
     items = SaleReturnItemDetailSerializer(many=True, read_only=True) # Qaytarilgan elementlar

     class Meta:
         model = SaleReturn
         fields = ['id', 'original_sale_id', 'reason', 'returned_by_username', 'created_at', 'total_returned_amount_uzs', 'items']


class PosProductSerializer(serializers.ModelSerializer):
    """POS ekrani uchun mahsulot ma'lumotlari (qoldiq bilan)"""
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    price_uzs = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    quantity_in_stock = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'barcode',
            'category_name', 'price_uzs', 'price_usd',
            'quantity_in_stock',
        ]
        # ---- Tekshiring ----
        read_only_fields = [ # LIST YOKI KORTEJ
            'id', 'name', 'barcode', 'category_name',
            'price_uzs', 'price_usd', 'quantity_in_stock'
        ]


class KassaTransactionSerializer(serializers.ModelSerializer):
    """Kassa amaliyotlarini ko'rsatish uchun"""
    kassa_name = serializers.CharField(source='kassa.name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True, allow_null=True)
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    related_sale_id = serializers.PrimaryKeyRelatedField(source='related_sale', read_only=True)
    related_payment_id = serializers.PrimaryKeyRelatedField(source='related_installment_payment', read_only=True)
    related_return_id = serializers.PrimaryKeyRelatedField(source='related_return', read_only=True)

    class Meta:
        model = KassaTransaction
        fields = [
            'id', 'kassa', 'kassa_name', 'amount', 'transaction_type', 'transaction_type_display',
            'user', 'user_username', 'comment', 'timestamp',
            'related_sale_id', 'related_payment_id', 'related_return_id'
        ]
        read_only_fields = fields # Odatda o'zgartirilmaydi

class BaseCashOperationSerializer(serializers.Serializer):
    """Kirim/Chiqim uchun asosiy serializer"""
    kassa_id = serializers.PrimaryKeyRelatedField(
        queryset=Kassa.objects.filter(is_active=True),
        label="Kassa"
    )
    amount = serializers.DecimalField(
        max_digits=17, decimal_places=2, min_value=Decimal('0.01'),
        label="Summa (UZS)"
    )
    comment = serializers.CharField(required=False, allow_blank=True, label="Izoh")

    def validate_kassa_id(self, kassa):
        # Qo'shimcha tekshiruvlar (masalan, user shu kassaga kira oladimi?)
        # permission_classes hal qilishi kerak
        return kassa

class CashInSerializer(BaseCashOperationSerializer):
    """Kassaga naqd pul kirimi uchun"""
    def save(self, **kwargs):
        validated_data = {**self.validated_data, **kwargs}
        kassa = validated_data['kassa_id']
        amount = validated_data['amount']
        comment = validated_data.get('comment')
        user = validated_data['user'] # Viewdan keladi

        transaction = KassaTransaction.objects.create(
            kassa=kassa,
            amount=amount,
            transaction_type=KassaTransaction.TransactionType.CASH_IN,
            user=user,
            comment=comment
        )
        return transaction

class CashOutSerializer(BaseCashOperationSerializer):
    """Kassadan naqd pul chiqimi (xarajat) uchun"""
    def save(self, **kwargs):
        validated_data = {**self.validated_data, **kwargs}
        kassa = validated_data['kassa_id']
        amount = validated_data['amount']
        comment = validated_data.get('comment')
        user = validated_data['user']

        # Balansni tekshirish (ixtiyoriy, lekin tavsiya etiladi)
        # current_balance = get_kassa_balance(kassa.id) # reports.services dan import qilish kerak
        # if current_balance is None or amount > current_balance:
        #     raise serializers.ValidationError(f"{kassa.name} kassasida yetarli mablag' yo'q (Mavjud: {current_balance:.2f} UZS).")

        transaction = KassaTransaction.objects.create(
            kassa=kassa,
            amount=amount, # Summa musbat saqlanadi, turi chiqimligini bildiradi
            transaction_type=KassaTransaction.TransactionType.CASH_OUT,
            user=user,
            comment=comment
        )
        return transaction

# SaleReturnSerializer ga refund_method qo'shish
class SaleReturnItemInputSerializer(serializers.Serializer):
    sale_item_id = serializers.PrimaryKeyRelatedField(queryset=SaleItem.objects.all(), label="Sotuv Elementi ID")
    quantity = serializers.IntegerField(min_value=1, label="Qaytariladigan miqdor")

class SaleReturnSerializer(serializers.Serializer):
    items_to_return = SaleReturnItemInputSerializer(many=True, required=True, min_length=1, label="Qaytariladigan mahsulotlar")
    reason = serializers.CharField(required=False, allow_blank=True, label="Qaytarish sababi")
    # Qaytarish usulini qo'shamiz
    refund_method = serializers.ChoiceField(
        choices=[('Naqd', 'Naqd Pul'), ('Karta', 'Kartaga'), ('None', "Pul qaytarilmaydi")], # Yoki boshqa variantlar
        default='Naqd', # Standart holatda naqd qaytariladi deb hisoblaymiz
        label="Pulni Qaytarish Usuli"
    )

    def validate_items_to_return(self, items):
        # ... (oldingi validatsiya logikasi: bitta sotuv, yetarli miqdor) ...
        if not items: raise serializers.ValidationError("...")
        sale_id = None
        sale_items_map = {}
        for item_data in items:
            sale_item_id = item_data['sale_item_id'].id
            quantity_to_return = item_data['quantity']
            try:
                sale_item = SaleItem.objects.select_related('sale__kassa', 'product').get(id=sale_item_id)
                sale_items_map[sale_item_id] = sale_item
            except SaleItem.DoesNotExist: raise serializers.ValidationError(...)

            current_sale_id = sale_item.sale_id
            if sale_id is None:
                sale_id = current_sale_id
                sale = sale_item.sale
                if not sale.can_be_returned: raise serializers.ValidationError(...)
                self.context['sale_instance'] = sale
            elif current_sale_id != sale_id: raise serializers.ValidationError(...)
            if quantity_to_return > sale_item.quantity_available_to_return: raise serializers.ValidationError(...)
        self.context['sale_items_to_process'] = sale_items_map
        return items

    @transaction.atomic
    def create(self, validated_data):
        # --- Importlar ---
        from installments.models import InstallmentPlan # Faqat kerak bo'lsa
        from decimal import Decimal

        items_data = validated_data['items_to_return']
        reason = validated_data.get('reason')
        refund_method = validated_data['refund_method'] # Qaytarish usuli
        user = validated_data['user'] # Viewdan keladi
        sale = self.context['sale_instance']
        sale_items_map = self.context['sale_items_to_process']
        kassa = sale.kassa

        total_returned_amount_uzs = Decimal(0)
        inventory_ops_to_create = []
        sale_items_to_update = []
        product_stock_updates = {}

        sale_return_obj = SaleReturn.objects.create(
            original_sale=sale, reason=reason, returned_by=user
        )

        for item_data in items_data:
            sale_item_id = item_data['sale_item_id'].id
            quantity_returned = item_data['quantity']
            sale_item = sale_items_map[sale_item_id]

            SaleReturnItem.objects.create(
                sale_return=sale_return_obj, sale_item=sale_item, quantity_returned=quantity_returned
            )

            sale_item.quantity_returned += quantity_returned
            sale_items_to_update.append(sale_item)

            product_id = sale_item.product_id
            product_stock_updates[product_id] = product_stock_updates.get(product_id, 0) + quantity_returned

            inventory_ops_to_create.append(InventoryOperation(
                product=sale_item.product, kassa=kassa, user=user, quantity=quantity_returned,
                operation_type=InventoryOperation.OperationType.RETURN,
                comment=f"Sotuv #{sale.id} qaytarish #{sale_return_obj.id}. Sabab: {reason or '-'}",
            ))
            total_returned_amount_uzs += sale_item.price_at_sale_uzs * quantity_returned

        sale_return_obj.total_returned_amount_uzs = total_returned_amount_uzs
        sale_return_obj.save()

        # Ombor qoldiqlarini yangilash
        stocks_to_update = ProductStock.objects.select_for_update().filter(
            product_id__in=product_stock_updates.keys(), kassa=kassa
        )
        for stock in stocks_to_update:
            stock.quantity += product_stock_updates[stock.product_id]
        ProductStock.objects.bulk_update(stocks_to_update, ['quantity'])

        # Operatsiya tarixini saqlash
        InventoryOperation.objects.bulk_create(inventory_ops_to_create)
        # Sotuv elementi qaytarilgan miqdorini saqlash
        SaleItem.objects.bulk_update(sale_items_to_update, ['quantity_returned'])

        # Sotuv statusini yangilash
        all_items = sale.items.all() # Barcha elementlarni olish
        if all(si.quantity_available_to_return == 0 for si in all_items):
            sale.status = Sale.SaleStatus.RETURNED
        else:
            sale.status = Sale.SaleStatus.PARTIALLY_RETURNED
        sale.save(update_fields=['status'])

        # Nasiya rejasini moslashtirish (agar bo'lsa)
        if sale.payment_type == Sale.PaymentType.INSTALLMENT:
            try:
                plan = sale.installmentplan
                plan.adjust_for_return(total_returned_amount_uzs)
                plan.save()
            except InstallmentPlan.DoesNotExist: pass # Xatolik bermaymiz
            except Exception as e: print(f"Error adjusting installment: {e}")

        # Kassaga qaytarilgan summani chiqim qilish (agar Naqd qaytarilgan bo'lsa)
        if refund_method == 'Naqd' and total_returned_amount_uzs > 0:
             KassaTransaction.objects.create(
                 kassa=kassa,
                 amount=total_returned_amount_uzs,
                 transaction_type=KassaTransaction.TransactionType.RETURN_REFUND,
                 user=user,
                 comment=f"Sotuv #{sale.id} uchun qaytarish #{sale_return_obj.id}",
                 related_return=sale_return_obj
             )

        # Javob sifatida yangilangan sotuv detalini qaytaramiz
        return SaleDetailSerializer(instance=sale, context=self.context).data
