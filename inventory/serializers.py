# inventory/serializers.py
from rest_framework import serializers
from django.db import transaction
from django.core.exceptions import PermissionDenied # Import qiling

# --- Model importlari ---
from .models import ProductStock, InventoryOperation
from products.models import Product, Kassa, Category # Category kerak emas


# --- Boshqa Serializer importlari ---
from products.serializers import ProductSerializer, KassaSerializer # UserSerializer kerak emas
from users.serializers import UserSerializer # Userni ko'rsatish uchun

# --- Ko'rsatish Uchun Serializerlar ---

class ProductStockSerializer(serializers.ModelSerializer):
    """Ombor qoldiqlarini ko'rsatish uchun serializer"""
    product = ProductSerializer(read_only=True)
    kassa = KassaSerializer(read_only=True)
    is_low_stock = serializers.ReadOnlyField() # Model propertydan olinadi


    class Meta:
        model = ProductStock
        fields = ['id', 'product', 'kassa', 'quantity', 'minimum_stock_level', 'is_low_stock']


class InventoryOperationSerializer(serializers.ModelSerializer):
    """Ombor amaliyotlari tarixini ko'rsatish uchun serializer"""
    product = ProductSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    kassa = KassaSerializer(read_only=True)
    operation_type_display = serializers.CharField(source='get_operation_type_display', read_only=True)
    related_operation_id = serializers.PrimaryKeyRelatedField(source='related_operation', read_only=True)


    class Meta:
        model = InventoryOperation
        fields = [
            'id',  'product', 'user', 'kassa', 'quantity',
            'operation_type', 'operation_type_display',
            'comment', 'timestamp', 'related_operation_id'
        ]


# --- Amaliyotlar uchun INPUT Serializerlar ---

class BaseInventoryOperationSerializer(serializers.Serializer):
    """Amaliyotlar uchun umumiy maydonlar va validatsiya (do'kon tekshiruvi bilan)"""
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), label="Mahsulot") # Do'kon bo'yicha filterlanadi
    quantity = serializers.IntegerField(min_value=1, label="Miqdor (Musbat)")
    comment = serializers.CharField(required=False, allow_blank=True, label="Izoh")



    def validate_product_id(self, product):
        """Mahsulotni validatsiya qiladi"""

        if not product.is_active:
             raise serializers.ValidationError("Mahsulot aktiv emas.")
        return product


class InventoryAddSerializer(BaseInventoryOperationSerializer):
    """Omborga mahsulot qo'shish uchun"""
    kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.all(), label="Qaysi kassaga") # Do'kon bo'yicha filterlanadi

    def validate_kassa_id(self, kassa):
        """Kassani validatsiya qiladi va superuser uchun store ni aniqlaydi"""
        if not kassa.is_active:
            raise serializers.ValidationError("Kassa aktiv emas.")
        return kassa




    def save(self, **kwargs):
        validated_data = {**self.validated_data, **kwargs} # request.user ni olish uchun
        product = validated_data['product_id']
        kassa = validated_data['kassa_id']
        quantity = validated_data['quantity'] # Musbat
        user = validated_data['user']
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
                quantity=quantity, # Musbat
                operation_type=InventoryOperation.OperationType.ADD,
                comment=comment
            )
        return InventoryOperationSerializer(operation, context=self.context).data


class InventoryRemoveSerializer(BaseInventoryOperationSerializer):
    """Ombordan mahsulot chiqarish uchun (sotuv emas)"""
    kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.all(), label="Qaysi kassadan")

    def validate_kassa_id(self, kassa):
        # InventoryAddSerializer dagi kabi tekshirish
        if not kassa.is_active:
            raise serializers.ValidationError("Kassa aktiv emas.")
        return kassa

    def validate(self, data):
        """Umumiy validatsiya va qoldiq tekshiruvi"""
        store = self.context.get('store')
        if not store:
             raise serializers.ValidationError("Do'kon aniqlanmadi.")
        product = data.get('product_id')
        kassa = data.get('kassa_id')
        quantity_to_remove = data['quantity'] # Musbat kiritilgan

        if product:
            self._validate_belongs_to_store(product, "Mahsulot", store)

        # Qoldiqni tekshirish
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
        quantity_to_remove = validated_data['quantity'] # Musbat
        user = validated_data['user']
        comment = validated_data.get('comment')
        store = self.context['store']

        if not user.is_superuser and (not hasattr(user, 'profile') or user.profile.store != store):
             raise PermissionDenied("Siz bu do'konda amaliyot bajara olmaysiz.")

        with transaction.atomic():
            stock = ProductStock.objects.select_for_update().get(product=product, kassa=kassa)
            stock.quantity -= quantity_to_remove
            stock.save()

            operation = InventoryOperation.objects.create(
                product=product, kassa=kassa, user=user,
                quantity=-quantity_to_remove, # Manfiy qilib saqlaymiz
                operation_type=InventoryOperation.OperationType.REMOVE,
                comment=comment
            )
        return InventoryOperationSerializer(operation, context=self.context).data


class InventoryTransferSerializer(BaseInventoryOperationSerializer):
    """Bir kassadan boshqasiga mahsulot ko'chirish"""
    from_kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.all(), label="Qayerdan")
    to_kassa_id = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.all(), label="Qayerga")

    def validate_from_kassa_id(self, kassa):
        """Chiqish kassasini validatsiya qiladi va store ni aniqlaydi"""
        store = self._get_user_store_from_context()
        user = self.context.get('request').user
        if user and user.is_superuser and not store:
            store = kassa.store
            self.context['store'] = store # Store ni contextga saqlash
        elif store:
            self._validate_belongs_to_store(kassa, "'Qayerdan' kassa", store)
        else:
            raise serializers.ValidationError("Do'kon aniqlanmadi.")
        if not kassa.is_active:
            raise serializers.ValidationError("'Qayerdan' kassa aktiv emas.")
        return kassa

    def validate_to_kassa_id(self, kassa):
         """Kirish kassasini validatsiya qiladi"""
         store = self.context.get('store') # from_kassa dan aniqlangan bo'lishi kerak
         if not store: # Agar from_kassa validatsiyasida xato bo'lsa
              store = self._get_user_store_from_context() # Qayta aniqlash
              user = self.context.get('request').user
              if user and user.is_superuser and not store:
                  store = kassa.store # Kirish kassasi orqali aniqlash
                  # Chiqish kassasi ham shu do'kondami?
                  from_kassa_pk = self.initial_data.get('from_kassa_id')
                  try:
                       if from_kassa_pk and Kassa.objects.get(pk=from_kassa_pk).store != store:
                            raise serializers.ValidationError("Chiqish va kirish kassalari turli do'konlarga tegishli.")
                  except Kassa.DoesNotExist: pass # from_kassa validatsiyasida xato beradi
              elif not store:
                   raise serializers.ValidationError("Do'kon aniqlanmadi.")

         self._validate_belongs_to_store(kassa, "'Qayerga' kassa", store)
         if not kassa.is_active:
             raise serializers.ValidationError("'Qayerga' kassa aktiv emas.")
         return kassa

    def validate(self, data):
         """Umumiy validatsiya va qoldiq tekshiruvi"""
         store = self.context.get('store')
         if not store:
              raise serializers.ValidationError("Do'kon aniqlanmadi.")

         from_kassa = data.get('from_kassa_id')
         to_kassa = data.get('to_kassa_id')
         product = data.get('product_id')
         quantity_to_transfer = data['quantity']

         if from_kassa == to_kassa:
             raise serializers.ValidationError({"to_kassa_id": "Chiqish va kirish kassalari bir xil bo'lishi mumkin emas."})

         if product:
             self._validate_belongs_to_store(product, "Mahsulot", store)

         # Qoldiqni tekshirish
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
        quantity = validated_data['quantity'] # Musbat
        user = validated_data['user']
        comment = validated_data.get('comment')
        store = self.context['store']

        if not user.is_superuser and (not hasattr(user, 'profile') or user.profile.store != store):
             raise PermissionDenied("Siz bu do'konda amaliyot bajara olmaysiz.")

        with transaction.atomic():
            # Chiqish kassasidan kamaytirish (locking bilan)
            from_stock = ProductStock.objects.select_for_update().get(product=product, kassa=from_kassa)
            # Qoldiqni qayta tekshirish (poyga holati uchun)
            if from_stock.quantity < quantity:
                  raise serializers.ValidationError(
                     f"{from_kassa.name} kassasida '{product.name}' dan yetarli emas (qayta tekshirish)."
                  )
            from_stock.quantity -= quantity
            from_stock.save()

            # Kirish kassasiga qo'shish (yoki yaratish, locking bilan)
            to_stock, created = ProductStock.objects.select_for_update().get_or_create(
                product=product, kassa=to_kassa,
                defaults={'quantity': 0}
            )
            to_stock.quantity += quantity
            to_stock.save()

            # Operatsiya tarixini juftlik qilib yozish
            out_operation = InventoryOperation.objects.create(
                product=product, kassa=from_kassa, user=user,
                quantity=-quantity, # Manfiy
                operation_type=InventoryOperation.OperationType.TRANSFER_OUT,
                comment=comment
            )
            in_operation = InventoryOperation.objects.create(
                product=product, kassa=to_kassa, user=user,
                quantity=quantity, # Musbat
                operation_type=InventoryOperation.OperationType.TRANSFER_IN,
                comment=comment,
                related_operation=out_operation
            )
            out_operation.related_operation = in_operation
            out_operation.save()

        # Kontekstni serializerlarga uzatish
        return {
            'transfer_out': InventoryOperationSerializer(out_operation, context=self.context).data,
            'transfer_in': InventoryOperationSerializer(in_operation, context=self.context).data
        }