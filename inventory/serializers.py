# inventory/serializers.py

from decimal import Decimal

from django.db.models import F
from django.utils import timezone
from rest_framework import serializers
from django.db import transaction

from sales.models import Sale
# from django.core.exceptions import PermissionDenied # Store tekshiruvi uchun kerak emas endi

# Model importlari
from .models import ProductStock, InventoryOperation, PurchaseOrder, PurchaseOrderItem, Supplier
from products.models import Product, Kassa
# from users.models import Store # Kerak emas

# Boshqa Serializer importlari
from products.serializers import ProductSerializer, KassaSerializer
from users.serializers import UserSerializer  # Userni ko'rsatish uchun


# --- Ko'rsatish Uchun Serializerlar ---

class ProductStockSerializer(serializers.ModelSerializer):
    """Ombor qoldiqlarini ko'rsatish uchun serializer"""
    product = ProductSerializer(read_only=True)
    kassa = KassaSerializer(read_only=True)
    is_low_stock = serializers.ReadOnlyField()

    class Meta:
        model = ProductStock
        fields = ['id', 'product', 'kassa', 'quantity', 'minimum_stock_level', 'is_low_stock']


class InventoryOperationSerializer(serializers.ModelSerializer):
    """Ombor amaliyotlari tarixini ko'rsatish uchun serializer"""
    product = ProductSerializer(read_only=True)
    user = UserSerializer(read_only=True, allow_null=True)  # user null bo'lishi mumkin
    kassa = KassaSerializer(read_only=True)
    operation_type_display = serializers.CharField(source='get_operation_type_display', read_only=True)
    related_operation_id = serializers.PrimaryKeyRelatedField(source='related_operation', read_only=True,
                                                              allow_null=True)  # null bo'lishi mumkin

    class Meta:
        model = InventoryOperation
        fields = [
            'id', 'product', 'user', 'kassa', 'quantity',
            'operation_type', 'operation_type_display',
            'comment', 'timestamp', 'related_operation_id'
        ]


# --- Amaliyotlar uchun INPUT Serializerlar ---

class BaseInventoryOperationSerializer(serializers.Serializer):
    """Amaliyotlar uchun umumiy maydonlar"""
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(is_active=True), label="Mahsulot")
    quantity = serializers.IntegerField(min_value=1, label="Miqdor (Musbat)")
    comment = serializers.CharField(required=False, allow_blank=True, label="Izoh")

    def validate_product_id(self, product):
        if not product.is_active:
            raise serializers.ValidationError("Mahsulot aktiv emas.")
        return product


class InventoryAddSerializer(BaseInventoryOperationSerializer):
    """Omborga mahsulot qo'shish uchun"""
    kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.filter(is_active=True), label="Qaysi kassaga")

    def validate_kassa_id(self, kassa):
        if not kassa.is_active:
            raise serializers.ValidationError("Kassa aktiv emas.")
        return kassa

    # Bu serializer uchun alohida validate() metodi shart emas, agar boshqa umumiy tekshiruv bo'lmasa

    def save(self, **kwargs):
        validated_data = {**self.validated_data, **kwargs}
        product = validated_data['product_id']
        kassa = validated_data['kassa_id']
        quantity = validated_data['quantity']
        user = validated_data['user']  # ViewSet.perform_create dan keladi
        comment = validated_data.get('comment')

        with transaction.atomic():
            stock, created = ProductStock.objects.select_for_update().get_or_create(
                product=product, kassa=kassa,
                defaults={'quantity': 0}
            )
            stock.quantity += quantity
            stock.save()

            operation = InventoryOperation.objects.create(
                product=product, kassa=kassa, user=user,
                quantity=quantity,  # Musbat
                operation_type=InventoryOperation.OperationType.ADD,
                comment=comment
            )
        # context ni uzatish kerak, agar InventoryOperationSerializer uni ishlatsa
        return InventoryOperationSerializer(operation, context=self.context).data


class InventoryRemoveSerializer(BaseInventoryOperationSerializer):
    """Ombordan mahsulot chiqarish uchun (sotuv emas)"""
    kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.filter(is_active=True), label="Qaysi kassadan")

    def validate_kassa_id(self, kassa):
        if not kassa.is_active:
            raise serializers.ValidationError("Kassa aktiv emas.")
        return kassa

    def validate(self, data):
        # Bu metod endi faqat qoldiqni tekshiradi
        product = data.get('product_id')
        kassa = data.get('kassa_id')
        quantity_to_remove = data['quantity']

        if not (product and kassa):  # Agar product_id yoki kassa_id validatsiyadan o'tmagan bo'lsa
            # Bu holat odatda individual validate_* metodlarida ushlanadi
            raise serializers.ValidationError("Mahsulot yoki kassa to'g'ri tanlanmagan.")

        try:
            stock = ProductStock.objects.get(product=product, kassa=kassa)
            if stock.quantity < quantity_to_remove:
                raise serializers.ValidationError(
                    f"{kassa.name} kassasida '{product.name}' dan yetarli emas "
                    f"(Mavjud: {stock.quantity}, Chiqarilmoqchi: {quantity_to_remove})."
                )
        except ProductStock.DoesNotExist:
            raise serializers.ValidationError(f"'{product.name}' mahsuloti {kassa.name} kassasida topilmadi.")
        return data

    def save(self, **kwargs):
        validated_data = {**self.validated_data, **kwargs}
        product = validated_data['product_id']
        kassa = validated_data['kassa_id']
        quantity_to_remove = validated_data['quantity']
        user = validated_data['user']
        comment = validated_data.get('comment')

        with transaction.atomic():
            stock = ProductStock.objects.select_for_update().get(product=product, kassa=kassa)
            # Qayta tekshiruv (poyga holati uchun)
            if stock.quantity < quantity_to_remove:
                raise serializers.ValidationError(
                    f"Omborda '{product.name}' dan yetarli emas (qayta tekshirish). "
                    f"Mavjud: {stock.quantity}, So'ralgan: {quantity_to_remove}."
                )
            stock.quantity -= quantity_to_remove
            stock.save()

            operation = InventoryOperation.objects.create(
                product=product, kassa=kassa, user=user,
                quantity=-quantity_to_remove,  # Manfiy
                operation_type=InventoryOperation.OperationType.REMOVE,
                comment=comment
            )
        return InventoryOperationSerializer(operation, context=self.context).data


class InventoryTransferSerializer(BaseInventoryOperationSerializer):
    """Bir kassadan boshqasiga mahsulot ko'chirish"""
    from_kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.filter(is_active=True), label="Qayerdan")
    to_kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.filter(is_active=True), label="Qayerga")

    def validate_from_kassa_id(self, kassa):
        if not kassa.is_active:
            raise serializers.ValidationError("'Qayerdan' kassa aktiv emas.")
        return kassa

    def validate_to_kassa_id(self, kassa):
        if not kassa.is_active:
            raise serializers.ValidationError("'Qayerga' kassa aktiv emas.")
        return kassa

    def validate(self, data):
        from_kassa = data.get('from_kassa_id')
        to_kassa = data.get('to_kassa_id')
        product = data.get('product_id')
        quantity_to_transfer = data['quantity']

        if not (from_kassa and to_kassa and product):
            raise serializers.ValidationError("Mahsulot, chiqish va kirish kassalari to'g'ri tanlanmagan.")

        if from_kassa == to_kassa:
            raise serializers.ValidationError(
                {"to_kassa_id": "Chiqish va kirish kassalari bir xil bo'lishi mumkin emas."})

        try:
            stock = ProductStock.objects.get(product=product, kassa=from_kassa)
            if stock.quantity < quantity_to_transfer:
                raise serializers.ValidationError(
                    f"{from_kassa.name} kassasida '{product.name}' dan yetarli emas "
                    f"(Mavjud: {stock.quantity}, Ko'chirilmoqchi: {quantity_to_transfer})."
                )
        except ProductStock.DoesNotExist:
            raise serializers.ValidationError(f"'{product.name}' mahsuloti {from_kassa.name} kassasida topilmadi.")
        return data

    def save(self, **kwargs):
        validated_data = {**self.validated_data, **kwargs}
        product = validated_data['product_id']
        from_kassa = validated_data['from_kassa_id']
        to_kassa = validated_data['to_kassa_id']
        quantity = validated_data['quantity']
        user = validated_data['user']
        comment = validated_data.get('comment')

        with transaction.atomic():
            from_stock = ProductStock.objects.select_for_update().get(product=product, kassa=from_kassa)
            if from_stock.quantity < quantity:  # Qayta tekshiruv
                raise serializers.ValidationError(
                    f"Chiqish kassasida '{product.name}' dan yetarli emas (qayta tekshirish)."
                )
            from_stock.quantity -= quantity
            from_stock.save()

            to_stock, created = ProductStock.objects.select_for_update().get_or_create(
                product=product, kassa=to_kassa,
                defaults={'quantity': 0}
            )
            to_stock.quantity += quantity
            to_stock.save()

            out_operation = InventoryOperation.objects.create(
                product=product, kassa=from_kassa, user=user, quantity=-quantity,
                operation_type=InventoryOperation.OperationType.TRANSFER_OUT, comment=comment
            )
            in_operation = InventoryOperation.objects.create(
                product=product, kassa=to_kassa, user=user, quantity=quantity,
                operation_type=InventoryOperation.OperationType.TRANSFER_IN, comment=comment,
                related_operation=out_operation
            )
            out_operation.related_operation = in_operation
            out_operation.save()
        return {
            'transfer_out': InventoryOperationSerializer(out_operation, context=self.context).data,
            'transfer_in': InventoryOperationSerializer(in_operation, context=self.context).data
        }


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'


class PurchaseOrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity_ordered = serializers.IntegerField(min_value=1)
    purchase_price_currency = serializers.DecimalField(max_digits=17, decimal_places=2, min_value=Decimal('0.01'))
    target_kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.filter(is_active=True))


class PurchaseOrderCreateSerializer(serializers.Serializer):
    supplier_id = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all(), required=False, allow_null=True)
    # Yangi yetkazib beruvchi uchun ma'lumotlar (agar supplier_id berilmasa)
    new_supplier_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    new_supplier_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    payment_method = serializers.ChoiceField(choices=PurchaseOrder.PurchasePaymentMethod.choices,
                                             required=False)  # Ixtiyoriy qilsak bo'ladi
    # ... (yangi supplier uchun boshqa maydonlar) ...

    order_date = serializers.DateTimeField(default=timezone.now)  # Yoki DateField
    currency = serializers.ChoiceField(choices=Sale.SaleCurrency.choices)# <<<--- O'ZGARTIRILDI
    amount_paid = serializers.DecimalField(max_digits=17, decimal_places=2, default=Decimal(0), min_value=Decimal(0))
    due_date_for_remaining = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    items = PurchaseOrderItemInputSerializer(many=True, required=True, min_length=1)

    def validate(self, data):
        supplier_id = data.get('supplier_id')
        new_supplier_name = data.get('new_supplier_name')
        if not supplier_id and not new_supplier_name:
            # Ikkalasidan biri bo'lishi kerak (yoki umuman ixtiyoriy qilish mumkin)
            # Hozircha, agar ikkalasi ham bo'lmasa, noma'lum yetkazib beruvchi bo'ladi
            pass
        if supplier_id and new_supplier_name:
            raise serializers.ValidationError(
                "Faqat 'supplier_id' yoki 'new_supplier_name' dan biri kiritilishi mumkin.")

        # amount_paid total_amount dan oshmasligini create da tekshiramiz
        return data

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        supplier_id = validated_data.pop('supplier_id', None)
        new_supplier_name = validated_data.pop('new_supplier_name', None)
        new_supplier_phone = validated_data.pop('new_supplier_phone', None)
        created_by_user = self.context['request'].user  # Viewdan keladi

        supplier_obj = None
        if supplier_id:
            supplier_obj = supplier_id  # Bu allaqachon Supplier obyekti
        elif new_supplier_name:
            supplier_obj, _ = Supplier.objects.get_or_create(
                name=new_supplier_name,
                defaults={'phone_number': new_supplier_phone}
            )

        total_purchase_amount = Decimal(0)
        for item in items_data:
            total_purchase_amount += item['purchase_price_currency'] * item['quantity_ordered']

        validated_data['total_amount'] = total_purchase_amount
        validated_data['supplier'] = supplier_obj
        validated_data['created_by'] = created_by_user

        purchase_order = PurchaseOrder.objects.create(**validated_data)
        purchase_order.update_payment_status()  # To'lov statusini birinchi marta hisoblash

        for item_data in items_data:
            PurchaseOrderItem.objects.create(
                purchase_order=purchase_order,
                product=item_data['product_id'],
                quantity_ordered=item_data['quantity_ordered'],
                purchase_price_currency=item_data['purchase_price_currency'],
                target_kassa=item_data['target_kassa_id']
            )

        # Bu yerda mahsulotlarni omborga avtomatik kirim QILMAYMIZ.
        # Bu alohida "Mahsulotni Qabul Qilish" operatsiyasi bo'lishi kerak.
        # Chunki buyurtma va qabul qilish har doim bir vaqtda bo'lmaydi.
        # PurchaseOrder.status shu uchun kerak.

        # Javobni formatlash uchun PurchaseOrderDetailSerializer kerak bo'ladi
        return purchase_order  # Hozircha modelni qaytaramiz


# Mahsulotni omborga qabul qilish uchun serializer
class ReceivePurchaseItemSerializer(serializers.Serializer):
    purchase_order_item_id = serializers.PrimaryKeyRelatedField(queryset=PurchaseOrderItem.objects.all())
    quantity_received_now = serializers.IntegerField(min_value=1)
    # received_to_kassa_id # Agar PurchaseOrderItem da target_kassa bo'lmasa, bu yerda so'rash kerak
    comment = serializers.CharField(required=False, allow_blank=True)

    def validate_quantity_received_now(self, value):
        # Bu qismni to'liq yozish kerak, itemning quantity_pending_receive dan oshmasligi kerak
        item_id = self.initial_data.get('purchase_order_item_id')
        if item_id:
            try:
                item = PurchaseOrderItem.objects.get(pk=item_id)
                if value > item.quantity_pending_receive:
                    raise serializers.ValidationError(
                        f"Faqat {item.quantity_pending_receive} dona qabul qilish mumkin.")
            except PurchaseOrderItem.DoesNotExist:
                pass  # Keyingi validatsiya xato beradi
        return value

    @transaction.atomic
    def save(self, **kwargs):
        user = kwargs.get('user')
        item = self.validated_data['purchase_order_item_id']
        quantity_received_now = self.validated_data['quantity_received_now']
        comment = self.validated_data.get('comment')

        # 1. PurchaseOrderItem ni yangilash
        item.quantity_received += quantity_received_now
        item.save(update_fields=['quantity_received'])

        # 2. ProductStock ga kirim qilish
        stock, _ = ProductStock.objects.get_or_create(
            product=item.product, kassa=item.target_kassa,
            defaults={'quantity': 0}
        )
        stock.quantity += quantity_received_now
        stock.save(update_fields=['quantity'])

        # 3. InventoryOperation yaratish
        InventoryOperation.objects.create(
            product=item.product, kassa=item.target_kassa, user=user,
            quantity=quantity_received_now,  # Kirim (+)
            operation_type=InventoryOperation.OperationType.ADD,  # Yoki maxsus PURCHASE_RECEIVE
            comment=f"Xarid #{item.purchase_order_id} dan qabul qilindi. Izoh: {comment or '-'}"
        )

        # 4. PurchaseOrder statusini yangilash
        order = item.purchase_order
        all_items_received = not order.items.filter(quantity_received__lt=F('quantity_ordered')).exists()
        if all_items_received:
            order.status = PurchaseOrder.PurchaseStatus.RECEIVED
        else:
            order.status = PurchaseOrder.PurchaseStatus.PARTIALLY_RECEIVED
        order.save(update_fields=['status'])

        return item  # Qabul qilingan itemni qaytarish


# Chiqish uchun serializerlar (List/Detail)
class PurchaseOrderItemDetailSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    target_kassa_name = serializers.CharField(source='target_kassa.name', read_only=True)
    item_total_amount = serializers.ReadOnlyField()
    quantity_pending_receive = serializers.ReadOnlyField()

    class Meta:
        model = PurchaseOrderItem
        fields = '__all__'


class PurchaseOrderDetailSerializer(serializers.ModelSerializer):
    supplier = SupplierSerializer(read_only=True)  # Yoki faqat nomi
    items = PurchaseOrderItemDetailSerializer(many=True, read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    remaining_amount_to_pay = serializers.ReadOnlyField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = '__all__'  # Yoki kerakli maydonlar


class PurchaseOrderListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    remaining_amount_to_pay = serializers.ReadOnlyField()
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = ['id', 'supplier_name', 'order_date', 'currency_choices', 'total_amount', 'amount_paid',
                  'remaining_amount_to_pay', 'status_display', 'payment_status_display',
                  'due_date_for_remaining', 'payment_method', 'payment_method_display']