# products/serializers.py
from rest_framework import serializers
from decimal import Decimal  # Narxlar uchun
from .models import Kassa, Category, Product
from .services import generate_unique_barcode_value  # To'g'ri nomlangan funksiya


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
                                    help_text="Shtrix-kod yoki IMEI. Agar bo'sh qoldirilsa va 'identifier_type'='auto_barcode' bo'lsa, avtomatik generatsiya qilinadi.")

    # Bu maydon faqat so'rovda keladi, modelga yozilmaydi
    identifier_type = serializers.ChoiceField(
        choices=[('auto_barcode', 'Shtrix Kod (Avto)'), ('manual_imei', 'IMEI (Qo\'lda)')],
        write_only=True,
        required=True,  # Frontend har doim bu maydonni yuborishi kerak
        help_text="Identifikator turini tanlang."
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'category_name',
            'barcode',
            'identifier_type',  # Bu maydon Meta.fields da bo'lishi kerak, chunki u serializer maydoni
            'price_uzs', 'price_usd', 'purchase_price_usd', 'purchase_price_uzs',
            'purchase_date', 'description', 'storage_capacity', 'color',
            'series_region', 'battery_health', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at', 'category_name')
        extra_kwargs = {
            'barcode': {'allow_null': True, 'required': False, 'allow_blank': True},
            'price_usd': {'allow_null': True, 'required': False, 'min_value': Decimal('0.00')},
            'price_uzs': {'allow_null': True, 'required': False, 'min_value': Decimal('0.00')},
            # ... (qolgan extra_kwargs)
        }

    def validate(self, data):
        identifier_type = data.get('identifier_type')
        barcode_or_imei_value = data.get('barcode')

        if identifier_type == 'manual_imei':
            if not barcode_or_imei_value:
                raise serializers.ValidationError(
                    {"barcode": "IMEI (Qo'lda) tanlangan bo'lsa, qiymat kiritilishi shart."})

        # Narx validatsiyasi
        price_usd = data.get('price_usd', getattr(self.instance, 'price_usd', None) if self.instance else None)
        price_uzs = data.get('price_uzs', getattr(self.instance, 'price_uzs', None) if self.instance else None)

        has_price_usd = isinstance(price_usd, Decimal) and price_usd > 0
        has_price_uzs = isinstance(price_uzs, Decimal) and price_uzs > 0

        if not (has_price_usd or has_price_uzs):
            raise serializers.ValidationError(
                {"price_uzs": "Sotish narxining USD yoki UZS qiymatlaridan kamida bittasi 0 dan katta bo'lishi shart.",
                 "price_usd": "Sotish narxining USD yoki UZS qiymatlaridan kamida bittasi 0 dan katta bo'lishi shart."}
            )

        if barcode_or_imei_value:
            instance = self.instance
            query = Product.objects.filter(barcode=barcode_or_imei_value)
            if instance: query = query.exclude(pk=instance.pk)
            if query.exists():
                raise serializers.ValidationError({"barcode": "Bu shtrix-kod yoki IMEI allaqachon mavjud."})
        return data

    def create(self, validated_data):
        # --- MUHIM: 'identifier_type' ni validated_data dan olib tashlaymiz ---
        identifier_type = validated_data.pop('identifier_type', 'auto_barcode')  # Agar kelmasa, default 'auto_barcode'

        if identifier_type == 'auto_barcode' and not validated_data.get('barcode'):
            category_instance = validated_data.get('category')  # Bu Category obyekti (agar yuborilgan bo'lsa)
            category_id_for_barcode = category_instance.id if category_instance else None

            prefix_len = 0
            if category_id_for_barcode:
                try:
                    cat = Category.objects.get(pk=category_id_for_barcode)
                    if cat.barcode_prefix:
                        prefix_len = len(str(cat.barcode_prefix).strip())
                except Category.DoesNotExist:
                    pass

            random_part_actual_length = max(1, 9 - prefix_len)  # Jami ~9 belgi uchun

            validated_data['barcode'] = generate_unique_barcode_value(
                category_id=category_id_for_barcode,
                data_length=random_part_actual_length
            )
            print(f"Avtomatik generatsiya qilingan shtrix-kod: {validated_data['barcode']}")

        # Endi validated_data da 'identifier_type' yo'q
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Update paytida ham 'identifier_type' ni olib tashlaymiz, chunki u model maydoni emas
        validated_data.pop('identifier_type', None)
        return super().update(instance, validated_data)


class ProductLabelDataSerializer(serializers.Serializer):
    name = serializers.CharField(read_only=True)
    barcode_image_base64 = serializers.CharField(read_only=True)
    barcode_number = serializers.CharField(read_only=True)
    storage_capacity = serializers.CharField(required=False, allow_null=True)
    battery_health = serializers.IntegerField(required=False, allow_null=True)
    series_region = serializers.CharField(required=False, allow_null=True)