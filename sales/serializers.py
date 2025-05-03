# sales/serializers.py
from decimal import Decimal

from rest_framework import serializers
from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from users.models import Store
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
    store_id = serializers.IntegerField(source='store.id', read_only=True)

    class Meta:
        model = Customer
        fields = ['id', 'store_id', 'full_name', 'phone_number', 'email', 'address', 'created_at']
        read_only_fields = ('created_at', 'store_id')

    def validate_phone_number(self, value):
        request = self.context.get('request')
        user = request.user if request else None
        store = None
        instance = self.instance

        # Store ni aniqlash
        if user:
            if hasattr(user, 'profile') and user.profile.store:
                store = user.profile.store
            elif user.is_superuser:
                store_id = request.data.get('store_id') if not instance else instance.store_id
                if store_id:
                    try: store = Store.objects.get(pk=store_id)
                    except Store.DoesNotExist: pass
                if not store and not instance: # Yaratishda store ID kerak
                    raise serializers.ValidationError("Mijoz do'koni aniqlanmadi (superuser store_id bermagan).")
                elif not store and instance: # Tahrirlashda instance dan olish kerak edi, demak xato
                    store = instance.store # Qayta urinish
        elif instance:
            store = instance.store

        if not store:
            raise serializers.ValidationError("Mijoz qaysi do'konga tegishli ekanligi aniqlanmadi.")

        # Do'kon ichida unikallik
        query = Customer.objects.filter(store=store, phone_number=value)
        if instance:
            query = query.exclude(pk=instance.pk)
        if query.exists():
            raise serializers.ValidationError(f"Bu telefon raqami '{store.name}' do'konida allaqachon mavjud.")
        return value


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
    store_name = serializers.CharField(source='store.name', read_only=True) # Do'kon nomi qo'shildi
    seller_username = serializers.CharField(source='seller.username', read_only=True, default=None)
    customer_name = serializers.CharField(source='customer.full_name', read_only=True, default=None)
    kassa_name = serializers.CharField(source='kassa.name', read_only=True)
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = Sale
        fields = [
            'id', 'store_name', 'seller_username', 'customer_name', 'kassa_name',
            'total_amount_uzs', 'total_amount_usd',
            'payment_type', 'payment_type_display', 'status', 'status_display', 'created_at', 'items_count'
        ]

    def get_items_count(self, obj):
         return obj.items.count()


class SaleDetailSerializer(SaleListSerializer):
    """Bitta sotuvning batafsil ma'lumotlari"""
    items = SaleItemSerializer(many=True, read_only=True)
    seller = UserSerializer(read_only=True)
    customer = CustomerSerializer(read_only=True)
    kassa = KassaSerializer(read_only=True)
    store = serializers.PrimaryKeyRelatedField(read_only=True) # Store ID ni ham qaytaramiz
    installment_plan_id = serializers.IntegerField(source='installmentplan.id', read_only=True, default=None)

    class Meta(SaleListSerializer.Meta):
        # store_name ni olib tashlab, store ID sini qo'shamiz yoki ikkalasini qoldiramiz
        fields = [f for f in SaleListSerializer.Meta.fields if f != 'store_name'] + [
             'store', 'items', 'seller', 'customer', 'kassa',
             'amount_paid_uzs', 'installment_plan_id'
         ]


# --- Yangi Sotuv Uchun INPUT Serializerlar ---

class SaleItemInputSerializer(serializers.Serializer):
    """Sotuv uchun kiruvchi mahsulot ma'lumoti"""
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True), # Keyinroq do'kon bo'yicha filterlanadi
        label="Mahsulot ID"
    )
    quantity = serializers.IntegerField(min_value=1, label="Miqdor")


class SaleCreateSerializer(serializers.Serializer):
    """Yangi sotuv yaratish uchun"""
    items = SaleItemInputSerializer(many=True, required=True, min_length=1, label="Mahsulotlar")
    payment_type = serializers.ChoiceField(choices=Sale.PaymentType.choices, label="To'lov turi")
    kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.all(), label="Kassa") # Do'kon bo'yicha filterlanadi
    customer_id = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), required=False, allow_null=True, label="Mijoz") # Do'kon bo'yicha filterlanadi
    amount_paid_uzs_initial = serializers.DecimalField(
        max_digits=17, decimal_places=2, required=False, default=Decimal(0), min_value=Decimal(0), # Default va min_value qo'shildi
        label="Boshlang'ich to'lov (Nasiya uchun)"
    )
    # store_id ni bu yerda qabul qilmaymiz, contextdan olamiz

    def _get_store_from_context(self):
        """Contextdan (request orqali) do'konni aniqlaydi"""
        request = self.context.get('request')
        user = request.user if request else None
        store = None
        if user:
            if hasattr(user, 'profile') and user.profile.store:
                store = user.profile.store
            elif user.is_superuser:
                # Superuser uchun kassa orqali aniqlashga harakat qilamiz
                # (validate metodida bajariladi)
                pass
        if not store and not (user and user.is_superuser): # Superuser bo'lmasa, store topilishi shart
             raise PermissionDenied("Sotuv yaratish uchun do'konga biriktirilmagansiz.")
        return store # None bo'lishi mumkin (superuser uchun)

    def validate_kassa_id(self, kassa):
        """Kassani validatsiya qiladi va superuser uchun store ni aniqlaydi"""
        store = self._get_store_from_context()
        user = self.context.get('request').user

        if user and user.is_superuser and not store:
            # Agar superuser bo'lsa va store hali aniqlanmagan bo'lsa, kassa orqali aniqlaymiz
            store = kassa.store
            self.context['store'] = store # Keyingi validatsiyalar uchun saqlaymiz

        elif store and kassa.store != store:
             raise serializers.ValidationError(f"Tanlangan kassa '{store.name}' do'koniga tegishli emas.")
        elif not store: # Agar store hali ham None bo'lsa (kassa orqali ham topilmadi)
             raise serializers.ValidationError("Sotuv do'koni aniqlanmadi.")

        if not kassa.is_active:
             raise serializers.ValidationError("Tanlangan kassa aktiv emas.")
        return kassa

    def validate_customer_id(self, customer):
         """Mijozni validatsiya qiladi"""
         store = self.context.get('store') # validate_kassa_id dan keyin store aniq bo'lishi kerak
         if not store: # Agar kassa validatsiyasida xatolik bo'lgan bo'lsa
              # Qayta aniqlashga harakat qilamiz (bu holat kam uchraydi)
              store = self._get_store_from_context()
              if not store and self.context.get('request').user.is_superuser:
                  # Agar superuser va kassa ham berilmagan bo'lsa, mijoz orqali store ni ololmaymiz
                  raise serializers.ValidationError("Do'kon aniqlanmadi (kassa ham, mijoz ham berilmagan).")
              elif not store:
                   raise serializers.ValidationError("Do'kon aniqlanmadi.")

         if customer and customer.store != store:
              raise serializers.ValidationError(f"Tanlangan mijoz '{store.name}' do'koniga tegishli emas.")
         return customer

    def validate_items(self, items):
        """Mahsulotlar ro'yxati va qoldiqlarini tekshiradi"""
        store = self.context.get('store')
        kassa = self.context.get('kassa_instance') # validate_kassa_id da saqlangan bo'lishi kerak

        if not store or not kassa:
            # validate_kassa_id da xatolik bo'lgan
            raise serializers.ValidationError("Do'kon yoki kassa aniqlanmadi (validate_items).")

        if not items:
            raise serializers.ValidationError("Sotuv uchun kamida bitta mahsulot tanlanishi kerak.")

        product_ids = []
        product_quantities = {}
        for item_data in items:
            product = item_data['product_id']
            # Mahsulot shu do'konga tegishlimi?
            if product.store != store:
                 raise serializers.ValidationError({
                     f"items[{items.index(item_data)}].product_id":
                     f"Mahsulot '{product.name}' (ID: {product.id}) '{store.name}' do'koniga tegishli emas."
                 })
            product_ids.append(product.id)
            product_quantities[product.id] = item_data['quantity']

        # Qoldiqlarni tekshirish (locking bilan)
        # select_for_update() tranzaksiya ichida ishlatilishi kerak (create metodida)
        # Bu yerda oddiy tekshiruv qilamiz, create da qayta tekshiramiz
        stocks = ProductStock.objects.filter(
            product_id__in=product_ids, kassa=kassa
        ).in_bulk(field_name='product_id')

        for product_id, quantity_to_sell in product_quantities.items():
            stock = stocks.get(product_id)
            if stock is None or stock.quantity < quantity_to_sell:
                available_qty = stock.quantity if stock else 0
                # Mahsulot nomini olish uchun bazaga murojaat
                try:
                     product_name = Product.objects.get(pk=product_id).name
                except Product.DoesNotExist:
                     product_name = f"ID={product_id}"
                raise serializers.ValidationError(
                    f"'{product_name}' uchun {kassa.name} kassasida yetarli qoldiq yo'q "
                    f"(Mavjud: {available_qty}, So'ralgan: {quantity_to_sell})."
                )

        return items

    def validate(self, data):
         """Umumiy validatsiya (to'lov turi, boshlang'ich to'lov)"""
         # validate_kassa_id va validate_customer_id chaqirilganidan keyin ishlaydi
         # Store contextda mavjud
         store = self.context.get('store')
         if not store:
             raise serializers.ValidationError("Do'kon aniqlanmadi (umumiy validatsiya).")

         payment_type = data['payment_type']
         customer = data.get('customer_id') # Bu Customer obyekti
         amount_paid_initial = data.get('amount_paid_uzs_initial', Decimal(0))

         if payment_type == Sale.PaymentType.INSTALLMENT:
             if not customer:
                 raise serializers.ValidationError({"customer_id": "Nasiya savdo uchun mijoz tanlanishi shart."})
             # Boshlang'ich to'lov umumiy summadan oshmasligini create() da tekshiramiz
         elif amount_paid_initial != Decimal(0):
             raise serializers.ValidationError({"amount_paid_uzs_initial": "Boshlang'ich to'lov faqat Nasiya savdo uchun kiritiladi."})

         # Kassani contextga saqlab qo'yish (validate_items da ishlatish uchun)
         self.context['kassa_instance'] = data.get('kassa_id')

         return data

    @transaction.atomic # Tranzaksiya boshlandi
    def create(self, validated_data):
        # --- Kerakli modellar va serializerlarni import qilish ---
        from installments.serializers import InstallmentPlanCreateSerializer # Nasiya uchun
        from decimal import Decimal # Decimal uchun

        # --- Contextdan ma'lumotlarni olish ---
        request = self.context['request']
        user = request.user
        store = self.context['store'] # Validatsiyada aniqlangan

        # --- Validated_data dan ma'lumotlarni olish ---
        items_data = validated_data['items']
        kassa = validated_data['kassa_id'] # Bu Kassa obyekti
        payment_type = validated_data['payment_type']
        customer = validated_data.get('customer_id') # Bu Customer obyekti yoki None
        amount_paid_initial = validated_data.get('amount_paid_uzs_initial', Decimal(0))

        # --- Qoldiqlarni qayta tekshirish (select_for_update bilan) ---
        product_ids = [item['product_id'].id for item in items_data]
        # Bloklash uchun qoldiqlarni olish
        stocks = ProductStock.objects.select_for_update().filter(
            product_id__in=product_ids, kassa=kassa
        ).in_bulk(field_name='product_id')

        total_usd = Decimal(0)
        total_uzs = Decimal(0)
        sale_items_to_create = []
        inventory_operations_to_create = []
        stocks_to_update_list = [] # bulk_update uchun list

        for item_data in items_data:
            product = item_data['product_id']
            quantity = item_data['quantity']
            stock = stocks.get(product.id)

            # Poyga holatini tekshirish (agar boshqa jarayon qoldiqni o'zgartirgan bo'lsa)
            if stock is None or stock.quantity < quantity:
                 # Qayta tekshirish (agar select_for_update dan keyin o'zgarish bo'lsa)
                 current_stock = ProductStock.objects.filter(product=product, kassa=kassa).first()
                 if current_stock is None or current_stock.quantity < quantity:
                      raise serializers.ValidationError(
                           f"'{product.name}' uchun qoldiq yetarli emas (qayta tekshirishda aniqlandi). "
                           f"Mavjud: {current_stock.quantity if current_stock else 0}, So'ralgan: {quantity}."
                      )
                 stock = current_stock # Yangi qoldiqni ishlatish
                 # stocks dict ni yangilash shart emas, chunki stocks_to_update_list ga qo'shamiz

            total_usd += product.price_usd * quantity
            total_uzs += product.price_uzs * quantity

            sale_items_to_create.append(SaleItem(
                product=product, quantity=quantity,
                price_at_sale_usd=product.price_usd, price_at_sale_uzs=product.price_uzs
                # sale keyinroq bog'lanadi
            ))
            inventory_operations_to_create.append(InventoryOperation(
                product=product, kassa=kassa, user=user, quantity=-quantity, # Chiqim (-)
                operation_type=InventoryOperation.OperationType.SALE
                # comment keyinroq bog'lanadi
            ))

            # Qoldiqni kamaytirish va yangilash uchun ro'yxatga qo'shish
            stock.quantity -= quantity
            stocks_to_update_list.append(stock)

        # --- Nasiya uchun boshlang'ich to'lovni tekshirish ---
        if payment_type == Sale.PaymentType.INSTALLMENT and amount_paid_initial > total_uzs:
            raise serializers.ValidationError({
                "amount_paid_uzs_initial": f"Boshlang'ich to'lov ({amount_paid_initial}) umumiy summadan ({total_uzs}) oshmasligi kerak."
            })

        # --- Asosiy Sotuv (Sale) obyektini yaratish ---
        sale = Sale.objects.create(
            store=store,
            seller=user,
            customer=customer,
            kassa=kassa,
            total_amount_usd=total_usd,
            total_amount_uzs=total_uzs,
            payment_type=payment_type,
            # Agar Nasiya bo'lsa boshlang'ich to'lov, aks holda umumiy summa to'langan hisoblanadi
            amount_paid_uzs=(amount_paid_initial if payment_type == Sale.PaymentType.INSTALLMENT else total_uzs),
            status=Sale.SaleStatus.COMPLETED # Boshlang'ich status
        )

        # --- Bog'liq obyektlarni yaratish va saqlash ---
        # SaleItem larga Sale ni bog'lash
        for sale_item in sale_items_to_create:
             sale_item.sale = sale
        SaleItem.objects.bulk_create(sale_items_to_create)

        # InventoryOperation larga izoh qo'shish
        for op in inventory_operations_to_create:
             op.comment = f"Sotuv #{sale.id}"
        InventoryOperation.objects.bulk_create(inventory_operations_to_create)

        # ProductStock qoldiqlarini yangilash
        ProductStock.objects.bulk_update(stocks_to_update_list, ['quantity'])

        # --- Kassa Tranzaksiyasini Yaratish ---
        transaction_amount = Decimal(0)
        transaction_type = None

        if payment_type == Sale.PaymentType.CASH:
            transaction_amount = total_uzs
            transaction_type = KassaTransaction.TransactionType.SALE
        elif payment_type == Sale.PaymentType.CARD:
            # Karta to'lovi uchun tranzaksiya yaratamizmi? Kelishuvga bog'liq.
            # Agar yaratilsa, u kassaga ta'sir qilmaydi.
            # Hozircha yaratmaymiz.
            pass
        elif payment_type == Sale.PaymentType.INSTALLMENT:
            transaction_amount = amount_paid_initial
            transaction_type = KassaTransaction.TransactionType.INSTALLMENT_PAYMENT # Boshlang'ich to'lov

        if transaction_amount > 0 and transaction_type:
            KassaTransaction.objects.create(
                store=store,
                kassa=kassa,
                amount=transaction_amount,
                transaction_type=transaction_type,
                user=user,
                comment=f"Sotuv #{sale.id} ({payment_type})",
                related_sale=sale
            )

        # --- Nasiya Rejasini Yaratish (agar kerak bo'lsa) ---
        if payment_type == Sale.PaymentType.INSTALLMENT:
            installment_data = {
                'sale': sale.pk,
                'customer': customer.pk,
                'total_due': total_uzs,
                'amount_paid': amount_paid_initial,
                # 'next_payment_date': ... # Agar frontend yuborsa yoki default logika
            }
            # InstallmentPlanCreateSerializer ga store ni uzatish kerak
            installment_serializer = InstallmentPlanCreateSerializer(data=installment_data, context=self.context)
            if installment_serializer.is_valid(raise_exception=True):
                 # Serializerning save metodiga store ni uzatish
                 installment_serializer.save(store=store)

        # --- Yaratilgan Sotuv Ma'lumotini Qaytarish ---
        # SaleDetailSerializer ga contextni uzatish muhim (masalan, request user)
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
                store=sale.store,
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
    # Product modelidagi asosiy maydonlar
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    price_uzs = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    # Qoldiqni alohida qo'shamiz (viewdan keladi)
    quantity_in_stock = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'barcode', # barcode ham kerak bo'lishi mumkin skanerlash uchun
            'category_name', 'price_uzs', 'price_usd', # price_usd ham kerak bo'lishi mumkin
            'quantity_in_stock'
        ]
        read_only_fields = fields # Bu serializer faqat o'qish uchun