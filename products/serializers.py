# products/serializers.py
from rest_framework import serializers
from decimal import Decimal
from django.db import transaction
from django.db.models import F
from .models import Kassa, Category, Product
from .services import generate_unique_barcode_value
from inventory.models import ProductStock, InventoryOperation
from django.contrib.auth.models import User # Yoki settings.AUTH_USER_MODEL


class KassaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kassa
        fields = ['id', 'name', 'location', 'is_active']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description','is_accessory_category', 'barcode_prefix']


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), write_only=True, required=False,
                                                  allow_null=True)
    barcode = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True,
                                    help_text="Shtrix-kod yoki IMEI...")
    identifier_type = serializers.ChoiceField(
        choices=[('auto_barcode', 'Shtrix Kod (Avtomatik)'), ('manual_barcode_unique', 'Shtrix Kod (Unikal, Qo\'lda)'),
                 ('manual_imei', 'IMEI (Qo\'lda)')],
        write_only=True, required=True, help_text="Identifikator turini tanlang."
    )
    default_kassa_id_for_new_stock = serializers.PrimaryKeyRelatedField(queryset=Kassa.objects.filter(is_active=True),
                                                                        source='default_kassa_for_new_stock',
                                                                        write_only=True, required=False,
                                                                        allow_null=True,
                                                                        label="Yangi mahsulot uchun standart kassa")
    default_kassa_name_for_new_stock = serializers.CharField(source='default_kassa_for_new_stock.name', read_only=True,
                                                             allow_null=True)
    add_to_stock_quantity = serializers.IntegerField(write_only=True, required=False, allow_null=False, default=0,
                                                     min_value=0,
                                                     label="Omborga boshlang'ich kirim miqdori (standart: 0)")

    # supplier_id va supplier (ForeignKey) o'rniga yangi matnli maydonlar
    # supplier_id = serializers.PrimaryKeyRelatedField(...) # OLIB TASHALDI
    # supplier_name = serializers.CharField(source='supplier.name', read_only=True, allow_null=True) # OLIB TASHALDI
    # supplier_phone = serializers.CharField(source='supplier.phone_number', read_only=True, allow_null=True) # OLIB TASHALDI

    # YANGI QO'SHILDI: Yetkazib beruvchi ma'lumotlari uchun matnli maydonlar
    supplier_name_manual = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True,
        label="Yetkazib Beruvchi Ismi (Qo'lda)"
    )
    supplier_phone_manual = serializers.CharField(
        max_length=20, required=False, allow_blank=True, allow_null=True,
        label="Yetkazib Beruvchi Telefon Raqami (Qo'lda)"
        # Bu yerga ham RegexValidator qo'shish mumkin, lekin modelda borligi kifoya
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'category_name',
            'barcode', 'identifier_type',
            'supplier_name_manual', 'supplier_phone_manual',  # YANGI MATNLI MAYDONLAR
            'price_uzs', 'price_usd', 'purchase_price_usd', 'purchase_price_uzs',
            'purchase_date', 'description', 'storage_capacity', 'color',
            'series_region', 'battery_health', 'is_active',
            'default_kassa_id_for_new_stock', 'default_kassa_name_for_new_stock',
            'add_to_stock_quantity',
            'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at', 'category_name', 'default_kassa_name_for_new_stock')
        # extra_kwargs o'zgarishsiz

    # validate, create, update metodlari yangi supplier_name_manual va supplier_phone_manual
    # maydonlarini avtomatik qabul qiladi va Product modeliga saqlaydi. Maxsus logika shart emas.
    # ... (validate, create, update metodlari avvalgidek qoladi) ...
    def validate(self, data):  # Bu metodning oldingi logikasi saqlanib qoladi
        identifier_type = data.get('identifier_type');
        barcode_or_imei_value = data.get('barcode')
        if identifier_type in ['manual_barcode_unique', 'manual_imei']:
            if not barcode_or_imei_value: raise serializers.ValidationError(
                {"barcode": f"'{identifier_type}' tanlangan bo'lsa, shtrix-kod/IMEI kiritilishi shart."})
        price_usd = data.get('price_usd', getattr(self.instance, 'price_usd', None) if self.instance else None)
        price_uzs = data.get('price_uzs', getattr(self.instance, 'price_uzs', None) if self.instance else None)
        has_price_usd = isinstance(price_usd, Decimal) and price_usd > 0
        has_price_uzs = isinstance(price_uzs, Decimal) and price_uzs > 0
        if not (has_price_usd or has_price_uzs): raise serializers.ValidationError(
            {"price_uzs": "Narx USD yoki UZS da 0 dan katta bo'lishi shart.",
             "price_usd": "Narx USD yoki UZS da 0 dan katta bo'lishi shart."})
        if barcode_or_imei_value:
            instance = self.instance;
            query = Product.objects.filter(barcode=barcode_or_imei_value)
            if instance: query = query.exclude(pk=instance.pk)
            if query.exists(): raise serializers.ValidationError(
                {"barcode": "Bu shtrix-kod yoki IMEI allaqachon mavjud."})
        return data

    @transaction.atomic
    def create(self, validated_data):  # BU METODNING BOSHLANISHI
        identifier_type = validated_data.pop('identifier_type', 'auto_barcode')
        initial_quantity_to_add = validated_data.pop('add_to_stock_quantity', 0)
        request = self.context.get('request')
        user_for_op = request.user if request and hasattr(request,
                                                          'user') and request.user.is_authenticated else None  # None ga o'zgartirdim

        if not user_for_op and initial_quantity_to_add > 0:
            admin_user = User.objects.filter(is_superuser=True, is_active=True).first()
            if not admin_user:
                raise serializers.ValidationError(
                    "Mahsulot kirimini qayd etish uchun operatsiyani bajargan foydalanuvchi (yoki tizim administratori) topilmadi."
                )
            user_for_op = admin_user

        if identifier_type == 'auto_barcode' and not validated_data.get('barcode'):
            category_instance = validated_data.get('category');
            category_id_for_barcode = category_instance.id if category_instance else None
            prefix_len = 0
            if category_id_for_barcode:
                try:
                    cat = Category.objects.get(pk=category_id_for_barcode)
                    if cat.barcode_prefix:  # BU QATOR TRY ICHIDA
                        prefix_len = len(str(cat.barcode_prefix).strip())
                except Category.DoesNotExist:
                    pass  # except bloki try bilan bir xil darajada
            random_part_actual_length = max(1,
                                            9 - prefix_len)  # Bu qator if category_id_for_barcode dan keyin, lekin create dan oldin
            validated_data['barcode'] = generate_unique_barcode_value(category_id=category_id_for_barcode,
                                                                      data_length=random_part_actual_length)

        # BU QATORNING INDENTATSIYASI TO'G'IRLANDI (create metodi ichida)
        product_instance = super().create(validated_data)

        target_kassa = product_instance.default_kassa_for_new_stock
        if not target_kassa:
            first_active_kassa = Kassa.objects.filter(is_active=True).order_by('id').first()
            if first_active_kassa:
                target_kassa = first_active_kassa

        if not target_kassa and initial_quantity_to_add > 0:
            raise serializers.ValidationError(
                {"default_kassa_id_for_new_stock": f"Omborga kirim uchun aktiv kassa topilmadi."})

        if target_kassa:
            stock, stock_created = ProductStock.objects.get_or_create(
                product=product_instance,
                kassa=target_kassa,
                defaults={'quantity': 0}
            )
            if initial_quantity_to_add > 0:
                stock.quantity = F('quantity') + initial_quantity_to_add
                stock.save()
                stock.refresh_from_db()

                operation_comment = f"{product_instance.name}"
                InventoryOperation.objects.create(
                    product=product_instance,
                    kassa=target_kassa,
                    user=user_for_op,
                    quantity=initial_quantity_to_add,
                    operation_type=InventoryOperation.OperationType.INITIAL,
                    comment=operation_comment
                )
            elif stock_created:
                print(
                    f"ProductStock for '{product_instance.name}' at Kassa '{target_kassa.name}' created with quantity 0.")
        return product_instance  # BU QATOR create METODINING OXIRIDA BO'LISHI KERAK

    # update metodi ham class ichida bo'lishi kerak
    def update(self, instance, validated_data):
        # Update paytida identifier_type va add_to_stock_quantity ni olib tashlash
        validated_data.pop('identifier_type', None)
        validated_data.pop('add_to_stock_quantity', None)
        return super().update(instance, validated_data)


class ProductLabelDataSerializer(serializers.Serializer):
    # ... (o'zgarishsiz)
    name = serializers.CharField(read_only=True)
    barcode_image_base64 = serializers.CharField(read_only=True)
    barcode_number = serializers.CharField(read_only=True)
    storage_capacity = serializers.CharField(required=False, allow_null=True)
    battery_health = serializers.IntegerField(required=False, allow_null=True)
    series_region = serializers.CharField(required=False, allow_null=True)

# # products/serializers.py
# from rest_framework import serializers
# from decimal import Decimal  # Narxlar uchun
# from .models import Kassa, Category, Product
# from .services import generate_unique_barcode_value  # To'g'ri nomlangan funksiya
#
#
# class KassaSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Kassa
#         fields = ['id', 'name', 'location', 'is_active']
#
#
# class CategorySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Category
#         fields = ['id', 'name', 'description', 'barcode_prefix']
#
#
# class ProductSerializer(serializers.ModelSerializer):
#     category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
#     category = serializers.PrimaryKeyRelatedField(
#         queryset=Category.objects.all(),
#         write_only=True, required=False, allow_null=True
#     )
#     barcode = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True,
#                                     help_text="Shtrix-kod yoki IMEI. Agar bo'sh qoldirilsa va 'identifier_type'='auto_barcode' bo'lsa, avtomatik generatsiya qilinadi.")
#
#     # Bu maydon faqat so'rovda keladi, modelga yozilmaydi
#     identifier_type = serializers.ChoiceField(
#         choices=[('auto_barcode', 'Shtrix Kod (Avto)'), ('manual_imei', 'IMEI (Qo\'lda)')],
#         write_only=True,
#         required=True,  # Frontend har doim bu maydonni yuborishi kerak
#         help_text="Identifikator turini tanlang."
#     )
#
#     class Meta:
#         model = Product
#         fields = [
#             'id', 'name', 'category', 'category_name',
#             'barcode',
#             'identifier_type',  # Bu maydon Meta.fields da bo'lishi kerak, chunki u serializer maydoni
#             'price_uzs', 'price_usd', 'purchase_price_usd', 'purchase_price_uzs',
#             'purchase_date', 'description', 'storage_capacity', 'color',
#             'series_region', 'battery_health', 'is_active',
#             'created_at', 'updated_at'
#         ]
#         read_only_fields = ('created_at', 'updated_at', 'category_name')
#         extra_kwargs = {
#             'barcode': {'allow_null': True, 'required': False, 'allow_blank': True},
#             'price_usd': {'allow_null': True, 'required': False, 'min_value': Decimal('0.00')},
#             'price_uzs': {'allow_null': True, 'required': False, 'min_value': Decimal('0.00')},
#             # ... (qolgan extra_kwargs)
#         }
#
#     def validate(self, data):
#         identifier_type = data.get('identifier_type')
#         barcode_or_imei_value = data.get('barcode')
#
#         if identifier_type == 'manual_imei':
#             if not barcode_or_imei_value:
#                 raise serializers.ValidationError(
#                     {"barcode": "IMEI (Qo'lda) tanlangan bo'lsa, qiymat kiritilishi shart."})
#
#         # Narx validatsiyasi
#         price_usd = data.get('price_usd', getattr(self.instance, 'price_usd', None) if self.instance else None)
#         price_uzs = data.get('price_uzs', getattr(self.instance, 'price_uzs', None) if self.instance else None)
#
#         has_price_usd = isinstance(price_usd, Decimal) and price_usd > 0
#         has_price_uzs = isinstance(price_uzs, Decimal) and price_uzs > 0
#
#         if not (has_price_usd or has_price_uzs):
#             raise serializers.ValidationError(
#                 {"price_uzs": "Sotish narxining USD yoki UZS qiymatlaridan kamida bittasi 0 dan katta bo'lishi shart.",
#                  "price_usd": "Sotish narxining USD yoki UZS qiymatlaridan kamida bittasi 0 dan katta bo'lishi shart."}
#             )
#
#         if barcode_or_imei_value:
#             instance = self.instance
#             query = Product.objects.filter(barcode=barcode_or_imei_value)
#             if instance: query = query.exclude(pk=instance.pk)
#             if query.exists():
#                 raise serializers.ValidationError({"barcode": "Bu shtrix-kod yoki IMEI allaqachon mavjud."})
#         return data
#
#     def create(self, validated_data):
#         # --- MUHIM: 'identifier_type' ni validated_data dan olib tashlaymiz ---
#         identifier_type = validated_data.pop('identifier_type', 'auto_barcode')  # Agar kelmasa, default 'auto_barcode'
#
#         if identifier_type == 'auto_barcode' and not validated_data.get('barcode'):
#             category_instance = validated_data.get('category')  # Bu Category obyekti (agar yuborilgan bo'lsa)
#             category_id_for_barcode = category_instance.id if category_instance else None
#
#             prefix_len = 0
#             if category_id_for_barcode:
#                 try:
#                     cat = Category.objects.get(pk=category_id_for_barcode)
#                     if cat.barcode_prefix:
#                         prefix_len = len(str(cat.barcode_prefix).strip())
#                 except Category.DoesNotExist:
#                     pass
#
#             random_part_actual_length = max(1, 9 - prefix_len)  # Jami ~9 belgi uchun
#
#             validated_data['barcode'] = generate_unique_barcode_value(
#                 category_id=category_id_for_barcode,
#                 data_length=random_part_actual_length
#             )
#             print(f"Avtomatik generatsiya qilingan shtrix-kod: {validated_data['barcode']}")
#
#         # Endi validated_data da 'identifier_type' yo'q
#         return super().create(validated_data)
#
#     def update(self, instance, validated_data):
#         # Update paytida ham 'identifier_type' ni olib tashlaymiz, chunki u model maydoni emas
#         validated_data.pop('identifier_type', None)
#         return super().update(instance, validated_data)
#
#
# class ProductLabelDataSerializer(serializers.Serializer):
#     name = serializers.CharField(read_only=True)
#     barcode_image_base64 = serializers.CharField(read_only=True)
#     barcode_number = serializers.CharField(read_only=True)
#     storage_capacity = serializers.CharField(required=False, allow_null=True)
#     battery_health = serializers.IntegerField(required=False, allow_null=True)
#     series_region = serializers.CharField(required=False, allow_null=True)