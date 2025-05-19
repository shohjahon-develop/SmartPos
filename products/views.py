# products/views.py
from rest_framework import viewsets, status, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import Kassa, Category, Product
from .serializers import *
from .services import generate_unique_barcode_value, generate_barcode_image  # YANGILANGAN IMPORTLAR


class KassaViewSet(viewsets.ModelViewSet):
    queryset = Kassa.objects.all().order_by('name')
    serializer_class = KassaSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    filterset_fields = ['is_active']
    search_fields = ['name', 'location']


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['name', 'barcode_prefix']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category').all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'barcode', 'description', 'category__name']
    ordering_fields = ['name', 'price_uzs', 'price_usd', 'created_at']

    def get_queryset(self):
        # ... (get_queryset logikasi avvalgidek qolishi mumkin) ...
        user = self.request.user
        queryset = Product.objects.select_related('category')
        if user.is_staff:
            is_active_param = self.request.query_params.get('is_active')
            if is_active_param is not None:
                is_active = is_active_param.lower() == 'true'
                return queryset.filter(is_active=is_active).order_by('name')
            return queryset.all().order_by('name')
        return queryset.filter(is_active=True).order_by('name')

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'generate_barcode', 'barcode_data']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data={'is_active': False}, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='generate-barcode')
    def generate_barcode(self, request):
        category_id_str = request.query_params.get('category_id')
        category_id = None
        if category_id_str:
            try:
                category_id = int(category_id_str)
            except ValueError:
                return Response({"error": "Noto'g'ri category_id formati."}, status=status.HTTP_400_BAD_REQUEST)

        barcode_number = generate_unique_barcode_value(  # YANGI FUNKSIYA
            category_id=category_id,
            data_length=10  # Misol, ehtiyojga qarab o'zgartiring
        )
        return Response({"barcode": barcode_number}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='barcode-data')
    def barcode_data(self, request, pk=None):
        product = self.get_object()
        if not product.barcode:
            return Response({"error": "Mahsulot uchun shtrix-kod mavjud emas."}, status=status.HTTP_404_NOT_FOUND)

        # barcode_image_type='Code128' (yoki services.py dagi default)
        barcode_image_base64 = generate_barcode_image(product.barcode, barcode_image_type='Code128')

        if not barcode_image_base64:
            return Response({"error": "Shtrix-kod rasmini generatsiya qilib bo'lmadi."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        price_display = "Narx belgilanmagan"
        if product.price_uzs is not None:
            price_display = f"{product.price_uzs} UZS"
        elif product.price_usd is not None:
            price_display = f"${product.price_usd}"

        data_for_serializer = {
            "name": product.name,
            "price_display_str": price_display,
            "barcode_image_base64": barcode_image_base64,
            "barcode_number": product.barcode
        }
        serializer = ProductLabelDataSerializer(
            instance=data_for_serializer)  # Bu serializer avvalgi javobda to'g'rilangan edi
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='print-label-data')
    def print_label_data(self, request, pk=None):
        product = self.get_object()

        barcode_to_print = product.barcode
        if not barcode_to_print:  # Agar barcode bo'sh bo'lsa, IMEI ni ham ishlatish mumkin (agar alohida saqlansa)
            # Agar IMEI barcode maydoniga yoziladigan bo'lsa, bu shart yetarli
            return Response({"error": "Chop etish uchun shtrix-kod/identifikator mavjud emas."},
                            status=status.HTTP_404_NOT_FOUND)

        # Rasm generatsiyasi (Code128 bilan)
        barcode_image_base64 = generate_barcode_image(barcode_to_print, barcode_image_type='Code128')

        if not barcode_image_base64:
            return Response({"error": "Shtrix-kod/IMEI rasmini generatsiya qilib bo'lmadi."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        label_data = {
            "name": product.name,
            "barcode_image_base64": barcode_image_base64,
            "barcode_number": barcode_to_print,
            "storage_capacity": product.storage_capacity,  # Xotirani qo'shamiz
        }

        # Kategoriya nomini tekshirib, iPhone uchun qo'shimcha ma'lumotlarni qo'shish
        if product.category and product.category.name and 'iphone' in product.category.name.lower():
            label_data["battery_health"] = product.battery_health
            label_data["series_region"] = product.series_region

        serializer = ProductLabelDataSerializer(instance=label_data)
        return Response(serializer.data)