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
    """Mahsulotlar CRUD operatsiyalari va shtrix-kod funksiyalari"""
    # store filtri olib tashlandi
    # is_active filtri qolishi mumkin
    queryset = Product.objects.select_related('category').all().order_by('name')
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_active'] # store filtri olib tashlandi
    search_fields = ['name', 'barcode', 'description', 'category__name']
    ordering_fields = ['name', 'price_usd', 'price_uzs', 'created_at', 'updated_at']

    # get_queryset metodini soddalashtirish
    def get_queryset(self):
         queryset = Product.objects.select_related('category').all()
         is_active_param = self.request.query_params.get('is_active')
         if is_active_param is not None:
             is_active = is_active_param.lower() == 'true'
             queryset = queryset.filter(is_active=is_active)
         # Agar faqat aktivlar kerak bo'lsa (admin bo'lmaganlar uchun)
         # elif not self.request.user.is_staff:
         #     queryset = queryset.filter(is_active=True)
         return queryset.order_by('name')

    # Agar faqat adminlar yaratishi/o'zgartirishi kerak bo'lsa:
    # --- RUXSATLARNI ANIQLASH METODI ---
    def get_permissions(self):
        """
        Actionga qarab kerakli ruxsatlarni qaytaradi.
        - Ko'rish (list, retrieve): Hamma autentifikatsiyadan o'tganlar.
        - Yaratish, Tahrirlash, O'chirish, Barcode: Faqat Admin/Superadmin.
        """
        # Agar action 'create', 'update', 'partial_update', 'destroy' bo'lsa
        # yoki bizning maxsus actionlar ('generate_barcode', 'barcode_data') bo'lsa:
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'generate_barcode', 'barcode_data']:
            # Faqat Admin yoki Superuser (IsAdminUser buni tekshiradi)
            permission_classes = [permissions.IsAdminUser]
        else:
            # Qolgan actionlar (list, retrieve) uchun:
            # Hamma autentifikatsiyadan o'tgan foydalanuvchi
            permission_classes = [permissions.IsAuthenticated]

        # Permission klasslaridan obyekt yaratib qaytarish
        return [permission() for permission in permission_classes]

        # perform_destroy o'rniga destroy ni override qilamiz
    def destroy(self, request, *args, **kwargs):
            """Mahsulotni o'chirish o'rniga nofaol holatga o'tkazadi."""
            instance = self.get_object()
            # instance.is_active = False # <<-- Nofaol qilamiz
            # instance.save(update_fields=['is_active']) # <<-- Faqat shu maydonni saqlaymiz
            # Yoki PATCH so'rovi bilan bir xil qilish uchun:
            serializer = self.get_serializer(instance, data={'is_active': False}, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)  # Bu instance.save() ni chaqiradi

            # Odatda DELETE 204 qaytaradi, lekin biz yangiladik, shuning uchun 200 OK qaytaramiz
            # Yoki 204 qaytarib, frontend o'zi yangilasa ham bo'ladi
            return Response(serializer.data, status=status.HTTP_200_OK)  # Nofaol

    # perform_create dan store ni belgilash olib tashlandi

    # generate_barcode va barcode_data o'zgarishsiz qoladi
    @action(detail=False, methods=['get'], url_path='generate-barcode')
    def generate_barcode(self, request):
        category_id_str = request.query_params.get('category_id')
        category_id = None
        if category_id_str:
            try:
                category_id = int(category_id_str)
            except ValueError:
                return Response({"error": "Noto'g'ri category_id formati."}, status=status.HTTP_400_BAD_REQUEST)

        # generate_unique_ean14_for_product endi to'liq EAN-14 kodini (checksum bilan) qaytaradi
        barcode_number = generate_unique_ean14_for_product(category_id=category_id)
        return Response({"barcode": barcode_number}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='barcode-data')
    def barcode_data(self, request, pk=None):
        product = self.get_object()
        if not product.barcode:
            return Response({"error": "Mahsulot uchun shtrix-kod mavjud emas."}, status=status.HTTP_404_NOT_FOUND)
        barcode_image_base64 = generate_barcode_image(product.barcode)
        if not barcode_image_base64:
            return Response({"error": "Shtrix-kod rasmini generatsiya qilib bo'lmadi."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        data_for_serializer = {
            "name": product.name, "price_uzs": product.price_uzs,
            "barcode_image_base64": barcode_image_base64, "barcode_number": product.barcode
        }
        serializer = BarcodeDataSerializer(instance=data_for_serializer)
        return Response(serializer.data)

