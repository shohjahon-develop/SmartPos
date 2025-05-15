# products/views.py
from rest_framework import viewsets, status, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
# Modellarni import qilish
from .models import Kassa, Category, Product
# Serializerlarni import qilish
from .serializers import KassaSerializer, CategorySerializer, ProductSerializer, BarcodeDataSerializer
# Servislarni import qilish
from .services import *
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly, IsAuthenticated

class KassaViewSet(viewsets.ModelViewSet):
    """Kassalar/Filiallar CRUD operatsiyalari"""
    queryset = Kassa.objects.all().order_by('name') # store filtri olib tashlandi
    serializer_class = KassaSerializer
    permission_classes = [permissions.IsAdminUser] # Faqat adminlar boshqaradi
    filter_backends = [filters.SearchFilter, DjangoFilterBackend] # Ordering kerak bo'lsa qo'shing
    filterset_fields = ['is_active'] # store filtri olib tashlandi
    search_fields = ['name', 'location']

    # perform_create dan store ni belgilash olib tashlandi


class CategoryViewSet(viewsets.ModelViewSet):
    """Mahsulot kategoriyalari CRUD operatsiyalari"""
    # store filtri olib tashlandi, faqat global kategoriyalar
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated] # Hamma ko'ra oladi
    search_fields = ['name']

    # Agar faqat adminlar yaratishi/o'zgartirishi kerak bo'lsa:
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    # perform_create dan store ni belgilash olib tashlandi


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category').all()  # .filter(is_active=True) ni vaqtincha oldim
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]  # Yoki IsAdminUser uchun alohida ruxsat
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'barcode', 'description', 'category__name']
    ordering_fields = ['name', 'price_uzs', 'price_usd', 'created_at']

    # get_queryset (agar adminlar nofaol mahsulotlarni ko'rishi kerak bo'lsa, avvalgidek)
    def get_queryset(self):
        user = self.request.user
        queryset = Product.objects.select_related('category')
        if user.is_staff:  # Adminlar hamma narsani ko'rsin
            is_active_param = self.request.query_params.get('is_active')
            if is_active_param is not None:
                is_active = is_active_param.lower() == 'true'
                return queryset.filter(is_active=is_active)
            return queryset.all()
        return queryset.filter(is_active=True)  # Oddiy userlar faqat aktivlarni

    @action(detail=False, methods=['get'], url_path='generate-barcode')
    def generate_barcode(self, request):
        category_id_str = request.query_params.get('category_id')
        category_id = None
        if category_id_str:
            try:
                category_id = int(category_id_str)
            except ValueError:
                return Response({"error": "Noto'g'ri category_id formati."}, status=status.HTTP_400_BAD_REQUEST)

        # data_length ni ehtiyojga qarab o'zgartiring
        barcode_number = generate_unique_barcode_value(
            category_id=category_id,
            data_length=12  # Misol
        )
        return Response({"barcode": barcode_number}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='barcode-data')
    def barcode_data(self, request, pk=None):
        product = self.get_object()
        if not product.barcode:
            return Response({"error": "Mahsulot uchun shtrix-kod mavjud emas."}, status=status.HTTP_404_NOT_FOUND)

        # Shtrix-kod turi (Code128 qavslarni yaxshi qo'llaydi)
        barcode_image_base64 = generate_barcode_image(product.barcode, barcode_image_type='Code128')

        if not barcode_image_base64:
            return Response({"error": "Shtrix-kod rasmini generatsiya qilib bo'lmadi."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        price_display = "Narx belgilanmagan"
        if product.price_uzs is not None:
            price_display = f"{product.price_uzs} UZS"
        elif product.price_usd is not None:
            price_display = f"${product.price_usd}"  # Yoki "USD " + str(product.price_usd)

        data_for_serializer = {
            "name": product.name,
            "price_uzs": price_display,  # Narxni bitta stringda ko'rsatish
            "barcode_image_base64": barcode_image_base64,
            "barcode_number": product.barcode
        }
        serializer = BarcodeDataSerializer(instance=data_for_serializer)
        return Response(serializer.data)
