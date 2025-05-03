# products/serializers.py
from rest_framework import serializers

from users.models import Store
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
    store_id = serializers.IntegerField(source='store.id', read_only=True)

    # Frontendda ko'rsatiladigan qoldiq maydoni (alohida endpointdan olinadi, bu yerda emas)
    # quantity_in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'store_id', 'name', 'category', 'category_name', 'barcode',
            # Sotish narxlari (USD kiritiladi, UZS o'qiladi)
            'price_usd', 'price_uzs',
            # Olingan narxlar (USD kiritiladi, UZS o'qiladi)
            'purchase_price_usd', 'purchase_price_uzs', 'purchase_date',
            # Boshqa xususiyatlar
            'description', 'storage_capacity', 'color', 'series_region', 'battery_health',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ('store_id', 'price_uzs', 'purchase_price_uzs', 'created_at', 'updated_at')
        # write_only bo'ladigan maydonlar: 'category'
        extra_kwargs = {
            'barcode': {'allow_null': True, 'required': False},
            'category': {'write_only': True},
            'description': {'allow_null': True, 'required': False},
            'storage_capacity': {'allow_null': True, 'required': False},
            'color': {'allow_null': True, 'required': False},
            'series_region': {'allow_null': True, 'required': False},
            'battery_health': {'allow_null': True, 'required': False},
            'purchase_price_usd': {'allow_null': True, 'required': False},
            'purchase_date': {'allow_null': True, 'required': False},
        }

    # def get_quantity_in_stock(self, obj):
    #     # Bu serializer universal bo'lgani uchun qoldiqni bu yerda olish samarasiz
    #     # Chunki qaysi kassa uchun qoldiq kerakligi noma'lum
    #     # Qoldiqni Inventory yoki POS endpointlarida olish kerak
    #     return None

    def validate_category(self, value):
        # Kategoriya joriy foydalanuvchining do'koniga tegishli ekanligini tekshirish
        request = self.context.get('request')
        if request and hasattr(request.user, 'profile') and request.user.profile.store:
            if value and value.store != request.user.profile.store and value.store is not None: # Global kategoriya (store=None) ham mumkin
                raise serializers.ValidationError("Tanlangan kategoriya sizning do'koningizga tegishli emas.")
        # Superuser uchun tekshirmaslik mumkin
        return value

    def validate_barcode(self, value):
        # Modelning save metodidagi tekshiruvni bu yerda ham qilish mumkin
        # (Request kontekstidan store ni olish kerak)
        instance = getattr(self, 'instance', None)
        request = self.context.get('request')
        user_store = None
        if request and hasattr(request.user, 'profile'):
            user_store = request.user.profile.store

        # Agar store aniqlanmagan bo'lsa (masalan, testlarda), validatsiyani o'tkazib yuborish
        if not user_store and not instance: # Yaratishda store bo'lishi kerak
             if not request.user.is_superuser: # Faqat superuser store tanlamasligi mumkin
                 raise serializers.ValidationError("Foydalanuvchi do'koni aniqlanmadi.")
             # Superuser uchun store_id request.data da kelishi kerak
             store_id = request.data.get('store') # Yoki 'store_id'
             if not store_id:
                  raise serializers.ValidationError("Mahsulot qaysi do'konga tegishli ekanligi ko'rsatilmagan.")
             try:
                  user_store = Store.objects.get(pk=store_id)
             except Store.DoesNotExist:
                  raise serializers.ValidationError("Ko'rsatilgan do'kon topilmadi.")

        # Agar tahrirlash bo'lsa, instance dan store olinadi
        store_to_check = user_store if not instance else instance.store

        if value and store_to_check:
            query = Product.objects.filter(store=store_to_check, barcode=value)
            if instance: # Tahrirlash holati
                query = query.exclude(pk=instance.pk)
            if query.exists():
                raise serializers.ValidationError(f"Bu shtrix-kod '{store_to_check.name}' do'konida allaqachon mavjud.")
        return value


class BarcodeDataSerializer(serializers.Serializer):
    """Shtrix-kodni chop etish uchun ma'lumotlar formati"""
    name = serializers.CharField(read_only=True)
    price_uzs = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    barcode_image_base64 = serializers.CharField(read_only=True) # Rasm (data URI)
    barcode_number = serializers.CharField(read_only=True) # Shtrix-kod raqami/matni