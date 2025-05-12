# inventory/serializers.py
from rest_framework import serializers
from django.db import transaction
# from django.core.exceptions import PermissionDenied # Store tekshiruvi uchun kerak emas endi

# Model importlari
from .models import ProductStock, InventoryOperation
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