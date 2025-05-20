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

    identifier_type = serializers.ChoiceField(
        choices=[('auto_barcode', 'Shtrix Kod (Avto)'), ('manual_imei', 'IMEI (Qo\'lda)')],
        write_only=True,
        required=True,
        help_text="Identifikator turini tanlang."
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'category_name',
            'barcode',
            'identifier_type',  # Faqat yozish uchun (request body da keladi)
            'price_uzs', 'price_usd', 'purchase_price_usd', 'purchase_price_uzs',
            'purchase_date', 'description', 'storage_capacity', 'color',
            'series_region', 'battery_health', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at', 'category_name')  # category_name ham read_only
        extra_kwargs = {
            'barcode': {'allow_null': True, 'required': False, 'allow_blank': True},
            'price_usd': {'allow_null': True, 'required': False, 'min_value': Decimal('0.00')},
            'price_uzs': {'allow_null': True, 'required': False, 'min_value': Decimal('0.00')},
            'purchase_price_usd': {'allow_null': True, 'required': False, 'min_value': Decimal('0.00')},
            'purchase_price_uzs': {'allow_null': True, 'required': False, 'min_value': Decimal('0.00')},
            'purchase_date': {'allow_null': True, 'required': False},
            'description': {'allow_null': True, 'required': False, 'allow_blank': True},
            'storage_capacity': {'allow_null': True, 'required': False, 'allow_blank': True},
            'color': {'allow_null': True, 'required': False, 'allow_blank': True},
            'series_region': {'allow_null': True, 'required': False, 'allow_blank': True},
            'battery_health': {'allow_null': True, 'required': False},
        }

    def validate(self, data):
        identifier_type = data.get('identifier_type')
        # barcode maydoni endi IMEI ni ham o'z ichiga olishi mumkin
        barcode_or_imei_value = data.get('barcode')

        if identifier_type == 'manual_imei':
            if not barcode_or_imei_value:
                raise serializers.ValidationError(
                    {"barcode": "IMEI (Qo'lda) tanlangan bo'lsa, qiymat kiritilishi shart."})

        # Narx validatsiyasi
        price_usd = data.get('price_usd', getattr(self.instance, 'price_usd', None) if self.instance else None)
        price_uzs = data.get('price_uzs', getattr(self.instance, 'price_uzs', None) if self.instance else None)
        if price_usd is None and price_uzs is None:
            # Agar ikkalasi ham None bo'lsa, kamida bittasini talab qilish
            # Yoki agar ikkalasi ham 0 bo'lsa (agar 0 ruxsat etilmagan narx bo'lsa)
            if not (isinstance(price_usd, Decimal) and price_usd > 0) and not (
                    isinstance(price_uzs, Decimal) and price_uzs > 0):
                raise serializers.ValidationError(
                    "Sotish narxining USD yoki UZS qiymatlaridan kamida bittasi 0 dan katta bo'lishi shart.")

        # Umumiy barcode/IMEI unikalligini tekshirish
        if barcode_or_imei_value:
            instance = self.instance
            query = Product.objects.filter(barcode=barcode_or_imei_value)
            if instance: query = query.exclude(pk=instance.pk)
            if query.exists():
                raise serializers.ValidationError({"barcode": "Bu shtrix-kod yoki IMEI allaqachon mavjud."})
        return data

    def create(self, validated_data):
        if not validated_data.get('barcode'):
            category_instance = validated_data.get('category')
            category_id_for_barcode = category_instance.id if category_instance else None

            # DATA_LENGTH NI 9 GA O'ZGARTIRAMIZ (YOKI PREFIKSNI HISOBGA OLGAN HOLDA)
            # Agar prefiks maksimal 2-3 belgi bo'lsa, random qism 6-7 belgi bo'lishi mumkin
            # Shunda jami uzunlik 9 atrofida bo'ladi.
            # Keling, random qismni qisqaroq qilamiz.
            prefix_len = 0
            if category_id_for_barcode:
                try:
                    cat = Category.objects.get(pk=category_id_for_barcode)
                    if cat.barcode_prefix:
                        prefix_len = len(str(cat.barcode_prefix).strip())
                except Category.DoesNotExist:
                    pass

            # Jami 9 ta belgi bo'lishini xohlasak:
            random_part_actual_length = max(1, 9 - prefix_len)  # Kamida 1 ta random belgi

            validated_data['barcode'] = generate_unique_barcode_value(
                category_id=category_id_for_barcode,
                data_length=random_part_actual_length
            )
            print(f"Avtomatik generatsiya qilingan shtrix-kod: {validated_data['barcode']}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('identifier_type', None)  # Update da bu maydonni e'tiborsiz qoldiramiz
        return super().update(instance, validated_data)


class ProductLabelDataSerializer(serializers.Serializer):
    name = serializers.CharField(read_only=True)
    barcode_image_base64 = serializers.CharField(read_only=True)
    barcode_number = serializers.CharField(read_only=True)
    storage_capacity = serializers.CharField(required=False, allow_null=True)
    battery_health = serializers.IntegerField(required=False, allow_null=True)
    series_region = serializers.CharField(required=False, allow_null=True)