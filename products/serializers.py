# products/serializers.py
from rest_framework import serializers
from .models import Kassa, Category, Product
from .services import generate_unique_barcode_value  # O'zgarmagan nom


class KassaSerializer(serializers.ModelSerializer):  # O'zgarishsiz
    class Meta: model = Kassa; fields = '__all__'


class CategorySerializer(serializers.ModelSerializer):  # O'zgarishsiz
    class Meta: model = Category; fields = '__all__'


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), write_only=True, required=False,
                                                  allow_null=True)

    # barcode endi IMEI ni ham qabul qiladi yoki avtomatik generatsiya bo'ladi
    barcode = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True,
                                    help_text="Shtrix-kod yoki IMEI. Agar bo'sh qoldirilsa va 'identifier_type'='auto_barcode' bo'lsa, avtomatik generatsiya qilinadi.")

    # Frontenddan qaysi turdagi identifikator ishlatilishini olish uchun
    identifier_type = serializers.ChoiceField(
        choices=[('auto_barcode', 'Shtrix Kod (Avto)'), ('manual_imei', 'IMEI (Qo\'lda)')],
        write_only=True,
        required=True,  # Majburiy tanlanishi kerak
        help_text="Identifikator turini tanlang."
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'category_name',
            'barcode',  # IMEI ham shu yerga yoziladi
            'identifier_type',  # Faqat yozish uchun
            'price_uzs', 'price_usd', 'purchase_price_usd', 'purchase_price_uzs',
            'purchase_date', 'description', 'storage_capacity', 'color',
            'series_region', 'battery_health', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')
        extra_kwargs = {
            'barcode': {'allow_null': True, 'required': False, 'allow_blank': True},
            # Endi bu required=False, chunki identifier_type ga bog'liq
            # ... (qolgan narx va boshqa maydonlar uchun extra_kwargs avvalgidek) ...
        }

    def validate(self, data):
        identifier_type = data.get('identifier_type')
        barcode_val = data.get('barcode')  # Bu IMEI bo'lishi ham mumkin

        if identifier_type == 'manual_imei':
            if not barcode_val:  # Agar IMEI tanlanib, qiymat kiritilmasa
                raise serializers.ValidationError(
                    {"barcode": "IMEI (Qo'lda) tanlangan bo'lsa, qiymat kiritilishi shart."})

        # Narx validatsiyasi (avvalgidek)
        price_usd = data.get('price_usd', getattr(self.instance, 'price_usd', None) if self.instance else None)
        price_uzs = data.get('price_uzs', getattr(self.instance, 'price_uzs', None) if self.instance else None)
        if price_usd is None and price_uzs is None:
            raise serializers.ValidationError(
                "Sotish narxining USD yoki UZS qiymatlaridan kamida bittasi kiritilishi shart.")

        # Umumiy barcode/IMEI unikalligini tekshirish
        if barcode_val:
            instance = self.instance
            query = Product.objects.filter(barcode=barcode_val)
            if instance: query = query.exclude(pk=instance.pk)
            if query.exists():
                raise serializers.ValidationError({"barcode": "Bu shtrix-kod yoki IMEI allaqachon mavjud."})
        return data

    def create(self, validated_data):
        if not validated_data.get('barcode'):  # Agar bo'sh bo'lsa yoki yuborilmasa
            category_instance = validated_data.get('category')
            category_id_for_barcode = category_instance.id if category_instance else None

            # Misol uchun, agar prefiks 2 raqamli, jami 12 raqamli kod kerak bo'lsa, data_length=10
            # Agar prefiks bo'lmasa, data_length=12 bo'ladi.
            # Yoki har doim bir xil uzunlikdagi random qism:
            random_part_len = 10  # Misol
            validated_data['barcode'] = generate_unique_barcode_value(
                category_id=category_id_for_barcode,
                data_length=random_part_len
            )
            print(f"Avtomatik generatsiya qilingan shtrix-kod: {validated_data['barcode']}")
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Update paytida identifier_type ni o'zgartirish logikasini qo'shish mumkin
        # Hozircha, agar barcode yuborilsa, u o'zgaradi.
        validated_data.pop('identifier_type', None)  # Update da bu maydonni ishlatmaymiz
        return super().update(instance, validated_data)


class ProductLabelDataSerializer(serializers.Serializer):
    name = serializers.CharField(read_only=True)
    # Narx maydoni OLIB TASHLA_NDI
    barcode_image_base64 = serializers.CharField(read_only=True)
    barcode_number = serializers.CharField(read_only=True)  # Bu DBdagi qiymat

    # Qo'shimcha ma'lumotlar (ixtiyoriy, viewda to'ldiriladi)
    storage_capacity = serializers.CharField(required=False, allow_null=True)  # Xotira uchun
    battery_health = serializers.IntegerField(required=False, allow_null=True)
    series_region = serializers.CharField(required=False, allow_null=True)