# products/serializers.py
from rest_framework import serializers

from .models import Kassa, Category, Product
from settings_app.models import CurrencyRate # Kursni olish uchun

class KassaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kassa
        fields = ['id', 'name', 'location', 'is_active']


class CategorySerializer(serializers.ModelSerializer):
    # store_id (agar avvalgi multi-tenantdan qolgan bo'lsa, olib tashlang)
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'barcode_prefix'] # barcode_prefix qo'shildi


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), write_only=True, required=False, allow_null=True,
        help_text="Mahsulot kategoriyasining ID si"
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'category_name', 'barcode',
            'price_usd', 'price_uzs',
            'purchase_price_usd', 'purchase_price_uzs', 'purchase_date',
            'description', 'storage_capacity', 'color', 'series_region', 'battery_health',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at') # price_uzs va purchase_price_uzs endi tahrirlanadigan
        extra_kwargs = {
            # ... (avvalgi extra_kwargs) ...
            'price_usd': {'allow_null': True, 'required': False},
            'price_uzs': {'allow_null': True, 'required': False},
            'purchase_price_usd': {'allow_null': True, 'required': False},
            'purchase_price_uzs': {'allow_null': True, 'required': False},
        }

    def validate(self, data):
        # Sotish narxlaridan kamida bittasi kiritilishi shart
        price_usd = data.get('price_usd', self.instance.price_usd if self.instance else None)
        price_uzs = data.get('price_uzs', self.instance.price_uzs if self.instance else None)

        if price_usd is None and price_uzs is None:
            raise serializers.ValidationError({
                "price_usd": "Sotish narxining USD yoki UZS qiymatlaridan kamida bittasi kiritilishi shart.",
                "price_uzs": "Sotish narxining USD yoki UZS qiymatlaridan kamida bittasi kiritilishi shart."
            })



        # Barcode validatsiyasi (store tekshiruvisiz)
        barcode = data.get('barcode', self.instance.barcode if self.instance else None)
        if barcode:
            query = Product.objects.filter(barcode=barcode)
            if self.instance:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise serializers.ValidationError({"barcode": "Bu shtrix-kod allaqachon mavjud."})

        # Category validatsiyasi (store tekshiruvisiz)
        # ... (agar kerak bo'lsa, category.store tekshiruvini olib tashlang) ...

        return data




class BarcodeDataSerializer(serializers.Serializer):
    """Shtrix-kodni chop etish uchun ma'lumotlar formati"""
    name = serializers.CharField(read_only=True)
    price_uzs = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    barcode_image_base64 = serializers.CharField(read_only=True)
    barcode_number = serializers.CharField(read_only=True)