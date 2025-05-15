# products/serializers.py
from rest_framework import serializers
from .models import Kassa, Category, Product
from .services import generate_unique_barcode_value  # Yangilangan funksiya nomi


class KassaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kassa
        fields = ['id', 'name', 'location', 'is_active']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'barcode_prefix']  # barcode_prefix qoldi


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        write_only=True, required=False, allow_null=True
    )
    barcode = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'category_name', 'barcode',
            'price_uzs', 'price_usd', 'purchase_price_usd', 'purchase_price_uzs',
            'purchase_date', 'description', 'storage_capacity', 'color',
            'series_region', 'battery_health', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')
        extra_kwargs = {
            'barcode': {'allow_null': True, 'required': False, 'allow_blank': True},
            'price_usd': {'allow_null': True, 'required': False},
            'price_uzs': {'allow_null': True, 'required': False},
            'purchase_price_usd': {'allow_null': True, 'required': False},
            'purchase_price_uzs': {'allow_null': True, 'required': False},
            'purchase_date': {'allow_null': True, 'required': False},
            'description': {'allow_null': True, 'required': False},
            'storage_capacity': {'allow_null': True, 'required': False},
            'color': {'allow_null': True, 'required': False},
            'series_region': {'allow_null': True, 'required': False},
            'battery_health': {'allow_null': True, 'required': False},
        }

    def validate(self, data):
        price_usd = data.get('price_usd', getattr(self.instance, 'price_usd', None) if self.instance else None)
        price_uzs = data.get('price_uzs', getattr(self.instance, 'price_uzs', None) if self.instance else None)
        if price_usd is None and price_uzs is None:
            raise serializers.ValidationError(
                "Sotish narxining USD yoki UZS qiymatlaridan kamida bittasi kiritilishi shart.")

        barcode_val = data.get('barcode')
        if barcode_val:
            instance = self.instance
            query = Product.objects.filter(barcode=barcode_val)
            if instance: query = query.exclude(pk=instance.pk)
            if query.exists():
                raise serializers.ValidationError({"barcode": "Bu shtrix-kod allaqachon mavjud."})
        return data

    def create(self, validated_data):
        if not validated_data.get('barcode'):
            category_instance = validated_data.get('category')
            category_id_for_barcode = category_instance.id if category_instance else None

            # DATA_LENGTH ni o'zingizga moslang, masalan, 10-12
            validated_data['barcode'] = generate_unique_barcode_value(
                category_id=category_id_for_barcode,
                data_length=12  # Misol uchun 12, prefiks bilan jami uzunlik kattaroq bo'ladi
            )
        return super().create(validated_data)





class BarcodeDataSerializer(serializers.Serializer):
    """Shtrix-kodni chop etish uchun ma'lumotlar formati"""
    name = serializers.CharField(read_only=True)
    price_uzs = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    barcode_image_base64 = serializers.CharField(read_only=True)
    barcode_number = serializers.CharField(read_only=True)