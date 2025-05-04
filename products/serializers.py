# products/serializers.py
from rest_framework import serializers

from .models import Kassa, Category, Product
from settings_app.models import CurrencyRate # Kursni olish uchun

class KassaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kassa
        fields = ['id', 'name', 'location', 'is_active']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), write_only=True, required=False, allow_null=True,
        help_text="Mahsulot kategoriyasining ID si"
    )
    # UZS narxlar faqat o'qish uchun
    price_uzs = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    purchase_price_uzs = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True, allow_null=True)
    # Do'kon ID sini ham ko'rsatamiz


    # Frontendda ko'rsatiladigan qoldiq maydoni (alohida endpointdan olinadi, bu yerda emas)
    # quantity_in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'category_name', 'barcode',
            'price_usd', 'price_uzs',
            'purchase_price_usd', 'purchase_price_uzs', 'purchase_date',
            'description', 'storage_capacity', 'color', 'series_region', 'battery_health',
            'is_active', 'created_at', 'updated_at'
        ]
        # ---- Tekshiring ----
        read_only_fields = ('price_uzs', 'purchase_price_uzs', 'created_at', 'updated_at')  # KORTEJ YOKI LIST



    def validate_barcode(self, value):
        # Store tekshiruvi kerak emas, faqat global unikallik
        instance = self.instance
        if value:
            query = Product.objects.filter(barcode=value)
            if instance:
                query = query.exclude(pk=instance.pk)
            if query.exists():
                raise serializers.ValidationError("Bu shtrix-kod allaqachon mavjud.")
        return value




class BarcodeDataSerializer(serializers.Serializer):
    """Shtrix-kodni chop etish uchun ma'lumotlar formati"""
    name = serializers.CharField(read_only=True)
    price_uzs = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    barcode_image_base64 = serializers.CharField(read_only=True)
    barcode_number = serializers.CharField(read_only=True)