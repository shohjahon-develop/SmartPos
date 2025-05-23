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
        fields = ['id', 'name', 'description', 'barcode_prefix']


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        write_only=True, required=False, allow_null=True
    )
    barcode = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True,
                                    help_text="Shtrix-kod / IMEI. Agar bo'sh qoldirilsa va 'identifier_type'='auto_barcode' bo'lsa, avtomatik generatsiya qilinadi.")

    # identifier_type qoladi, lekin uning add_to_stock_quantity ga ta'siri kamayadi
    identifier_type = serializers.ChoiceField(
        choices=[
            ('auto_barcode', 'Shtrix Kod (Avtomatik)'), # Aksessuarlar yoki umumiy shtrix-kodli mahsulotlar uchun
            ('manual_barcode_unique', 'Shtrix Kod (Unikal, Qo\'lda)'), # Har biri alohida hisoblanadigan mahsulotlar uchun (masalan, telefon)
            ('manual_imei', 'IMEI (Qo\'lda)') # Telefonlar uchun (agar IMEI ishlatilsa)
        ],
        write_only=True,
        required=True,
        help_text="Identifikator turini tanlang."
    )

    default_kassa_id_for_new_stock = serializers.PrimaryKeyRelatedField(
        queryset=Kassa.objects.filter(is_active=True),
        source='default_kassa_for_new_stock',
        write_only=True,
        required=False,
        allow_null=True,
        label="Yangi mahsulot uchun standart kassa"
    )
    default_kassa_name_for_new_stock = serializers.CharField(
        source='default_kassa_for_new_stock.name',
        read_only=True,
        allow_null=True
    )

    # O'ZGARTIRILDI: Bu maydon endi majburiy emas, default 0 bo'ladi. Frontend uni kerakli qiymat bilan yuborishi kerak.
    add_to_stock_quantity = serializers.IntegerField(
        write_only=True,
        required=False, # Majburiy emas, agar yuborilmasa 0 bo'ladi
        allow_null=False, # Null bo'lishi mumkin emas, 0 bo'lishi kerak
        default=0,       # Default qiymati 0
        min_value=0,     # Minimal qiymat 0
        label="Omborga boshlang'ich kirim miqdori (standart: 0)"
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'category_name',
            'barcode',
            'identifier_type',
            'price_uzs', 'price_usd', 'purchase_price_usd', 'purchase_price_uzs',
            'purchase_date', 'description', 'storage_capacity', 'color',
            'series_region', 'battery_health', 'is_active',
            'default_kassa_id_for_new_stock',
            'default_kassa_name_for_new_stock',
            'add_to_stock_quantity',
            'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at', 'category_name', 'default_kassa_name_for_new_stock')
        extra_kwargs = {
            'barcode': {'allow_null': True, 'required': False, 'allow_blank': True},
            'price_usd': {'allow_null': True, 'required': False, 'min_value': Decimal('0.00')},
            'price_uzs': {'allow_null': True, 'required': False, 'min_value': Decimal('0.00')},
        }

    def validate(self, data):
        identifier_type = data.get('identifier_type')
        barcode_or_imei_value = data.get('barcode')
        add_to_stock_quantity = data.get('add_to_stock_quantity', 0) # Default 0 olamiz, agar kelmasa

        # Agar 'manual_barcode_unique' yoki 'manual_imei' tanlansa, barcode kiritilishi shart
        if identifier_type in ['manual_barcode_unique', 'manual_imei']:
            if not barcode_or_imei_value:
                raise serializers.ValidationError(
                    {"barcode": f"'{identifier_type}' tanlangan bo'lsa, shtrix-kod/IMEI kiritilishi shart."})

        # add_to_stock_quantity validatsiyasi (min_value=0 allaqachon tekshiradi)
        # Agar qo'shimcha logika kerak bo'lsa, shu yerga qo'shiladi.
        # Masalan, identifier_type='manual_barcode_unique' bo'lsa va quantity > 1 bo'lsa, ogohlantirish berish
        if identifier_type in ['manual_barcode_unique', 'manual_imei'] and add_to_stock_quantity > 1:
             # Bu shunchaki ogohlantirish bo'lishi mumkin, yoki qattiq xatolik. Hozircha o'tkazamiz.
             print(f"WARNING: Unikal mahsulot '{barcode_or_imei_value}' uchun boshlang'ich miqdor {add_to_stock_quantity} kiritildi. Odatda 1 bo'lishi kerak.")


        # Narx validatsiyasi (o'zgarishsiz)
        price_usd = data.get('price_usd', getattr(self.instance, 'price_usd', None) if self.instance else None)
        price_uzs = data.get('price_uzs', getattr(self.instance, 'price_uzs', None) if self.instance else None)
        has_price_usd = isinstance(price_usd, Decimal) and price_usd > 0
        has_price_uzs = isinstance(price_uzs, Decimal) and price_uzs > 0
        if not (has_price_usd or has_price_uzs):
            raise serializers.ValidationError(
                {"price_uzs": "Sotish narxining USD yoki UZS qiymatlaridan kamida bittasi 0 dan katta bo'lishi shart.",
                 "price_usd": "Sotish narxining USD yoki UZS qiymatlaridan kamida bittasi 0 dan katta bo'lishi shart."}
            )

        # Barcode unikalligi (o'zgarishsiz)
        if barcode_or_imei_value:
            instance = self.instance
            query = Product.objects.filter(barcode=barcode_or_imei_value)
            if instance: query = query.exclude(pk=instance.pk)
            if query.exists():
                raise serializers.ValidationError({"barcode": "Bu shtrix-kod yoki IMEI allaqachon mavjud."})
        return data

    @transaction.atomic
    def create(self, validated_data):
        identifier_type = validated_data.pop('identifier_type', 'auto_barcode')
        # O'ZGARTIRILDI: add_to_stock_quantity endi default 0 bilan keladi (agar yuborilmasa)
        initial_quantity_to_add = validated_data.pop('add_to_stock_quantity', 0)

        request = self.context.get('request')
        user_for_op = request.user if request and hasattr(request, 'user') and request.user.is_authenticated else None
        if not user_for_op:
            system_user = User.objects.filter(is_superuser=True).first()
            if not system_user:
                 # Agar kirim miqdori 0 dan katta bo'lsa va user topilmasa, xatolik berish
                 if initial_quantity_to_add > 0:
                    raise serializers.ValidationError("Mahsulot kirimini qayd etish uchun foydalanuvchi topilmadi.")
                 # Agar kirim miqdori 0 bo'lsa, foydalanuvchisiz davom etish (masalan, "Tizim" deb yozish)
                 # Lekin InventoryOperation da user null=True, blank=True bo'lishi kerak
            user_for_op = system_user # Bu yerda user null bo'lishi mumkin, InventoryOperation modeli bunga mos bo'lishi kerak


        # Barcode generatsiyasi
        if identifier_type == 'auto_barcode' and not validated_data.get('barcode'):
            category_instance = validated_data.get('category')
            category_id_for_barcode = category_instance.id if category_instance else None
            prefix_len = 0
            if category_id_for_barcode:
                try:
                    cat = Category.objects.get(pk=category_id_for_barcode)
                    if cat.barcode_prefix:
                        prefix_len = len(str(cat.barcode_prefix).strip())
                except Category.DoesNotExist: pass
            random_part_actual_length = max(1, 9 - prefix_len)
            validated_data['barcode'] = generate_unique_barcode_value(
                category_id=category_id_for_barcode,
                data_length=random_part_actual_length
            )

        # 1. Product yaratish
        product_instance = super().create(validated_data)

        # 2. ProductStock yaratish/yangilash va InventoryOperation yaratish
        # initial_quantity_to_add 0 yoki undan katta bo'lishi mumkin
        target_kassa = product_instance.default_kassa_for_new_stock
        if not target_kassa:
            first_active_kassa = Kassa.objects.filter(is_active=True).order_by('id').first()
            if first_active_kassa:
                target_kassa = first_active_kassa
            else:
                if initial_quantity_to_add > 0: # Faqat kirim qilmoqchi bo'lsak kassa muhim
                    raise serializers.ValidationError({
                        "default_kassa_id_for_new_stock": f"Mahsulotni '{product_instance.name}' omborga ({initial_quantity_to_add} dona) kirim qilish uchun aktiv kassa topilmadi."
                    })
                else: # Agar kirim 0 bo'lsa, kassa yo'qligi muammo emas
                    print(f"INFO: Product '{product_instance.name}' uchun ProductStock yaratilmadi (kirim miqdori 0 va kassa topilmadi/belgilanmagan).")
                    return product_instance

        if target_kassa: # Kassa mavjud bo'lsagina davom etamiz
            stock, stock_created = ProductStock.objects.get_or_create(
                product=product_instance,
                kassa=target_kassa,
                defaults={'quantity': 0} # Avval 0 bilan yaratamiz (agar yangi bo'lsa)
            )

            if initial_quantity_to_add > 0:
                stock.quantity = F('quantity') + initial_quantity_to_add # Poyga holatini oldini olish uchun F()
                stock.save()
                stock.refresh_from_db() # Yangilangan qiymatni olish

                InventoryOperation.objects.create(
                    product=product_instance,
                    kassa=target_kassa,
                    user=user_for_op,
                    quantity=initial_quantity_to_add,
                    operation_type=InventoryOperation.OperationType.INITIAL, # Yoki ADD
                    comment=f"Yangi mahsulot '{product_instance.name}' tizimga kiritildi va omborga {initial_quantity_to_add} dona qo'shildi."
                )
                print(f"SUCCESS: ProductStock for '{product_instance.name}' at Kassa '{target_kassa.name}'. Quantity added: {initial_quantity_to_add}. New total: {stock.quantity}")
            elif stock_created: # Agar kirim miqdori 0 bo'lsa, lekin stock yozuvi yangi yaratilgan bo'lsa
                print(f"SUCCESS: ProductStock for '{product_instance.name}' at Kassa '{target_kassa.name}' created with quantity 0.")

        return product_instance

    def update(self, instance, validated_data):
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