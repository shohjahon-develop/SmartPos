# products/views.py
from django.db.models import Q
from rest_framework import viewsets, status, filters, permissions, serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from users.models import Store
from .models import Kassa, Category, Product
from .serializers import KassaSerializer, CategorySerializer, ProductSerializer, BarcodeDataSerializer
from .services import generate_unique_barcode_number, generate_barcode_image
# from users.permissions import IsAdminRole # Yoki Django admin
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly

class KassaViewSet(viewsets.ModelViewSet):
    """Kassalar/Filiallar CRUD operatsiyalari"""
    queryset = Kassa.objects.all()
    serializer_class = KassaSerializer
    permission_classes = [IsAdminUser] # Faqat adminlar boshqaradi
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'location']

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Kassa.objects.all()  # Superuser hammasini ko'radi
        if hasattr(user, 'profile') and user.profile.store:
            return Kassa.objects.filter(store=user.profile.store)
        return Kassa.objects.none()

    def perform_create(self, serializer):
        # Avtomatik ravishda joriy userning do'koniga bog'lash
        user = self.request.user
        if hasattr(user, 'profile') and user.profile.store:
            serializer.save(store=user.profile.store)
        elif user.is_superuser:
            # Superuser uchun store_id frontenddan kelishi kerak
            store_id = self.request.data.get('store_id')
            if not store_id: raise serializers.ValidationError({"store_id": "Do'kon ID si ko'rsatilmagan."})
            try:
                store = Store.objects.get(pk=store_id)
            except Store.DoesNotExist:
                raise serializers.ValidationError({"store_id": "Bunday do'kon topilmadi."})
            serializer.save(store=store)
        else:
            raise PermissionDenied("Kassa yaratish uchun do'konga biriktirilmagansiz.")


class CategoryViewSet(viewsets.ModelViewSet):
    """Mahsulot kategoriyalari CRUD operatsiyalari"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    # Adminlar o'zgartira oladi, hamma ko'ra oladi
    permission_classes = [IsAuthenticatedOrReadOnly] # Agar IsAdminUser bo'lsa, faqat admin
    search_fields = ['name']

    def get_permissions(self):
        # Yaratish, yangilash, o'chirish uchun Admin ruxsati kerak
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticatedOrReadOnly()]

    def get_queryset(self):
        user = self.request.user
        # Global (store=None) va userning do'koni kategoriyalarini ko'rsatish
        store_filter = Q(store=None)  # Global kategoriyalar
        if hasattr(user, 'profile') and user.profile.store:
            store_filter |= Q(store=user.profile.store)  # Yoki userning do'koni
        elif user.is_superuser:
            # Superuser hamma do'kon kategoriyalarini yoki faqat global ko'rishi mumkin
            # Hozircha global va o'z do'koninikini (agar bo'lsa) qaytaramiz
            pass  # store_filter o'zgarishsiz qoladi (faqat global) yoki hamma narsani qaytarish
            # return Category.objects.all() # Superuser uchun hamma narsa
        return Category.objects.filter(store_filter)

    def perform_create(self, serializer):
        user = self.request.user
        # Kategoriyani global (store=None) yoki userning do'koniga bog'lash
        # Frontend 'is_global' yoki shunga o'xshash flag yuborishi mumkin
        # Yoki superuser yaratganda global, admin yaratganda o'z do'koniga
        make_global = self.request.data.get('is_global', False) and user.is_superuser
        store_to_assign = None
        if not make_global:
            if hasattr(user, 'profile') and user.profile.store:
                store_to_assign = user.profile.store
            elif user.is_superuser:
                # Agar global bo'lmasa, superuser ham qaysidir do'kon uchun yaratishi kerak
                store_id = self.request.data.get('store_id')
                if not store_id: raise serializers.ValidationError(
                    {"store_id": "Do'kon ID si ko'rsatilmagan (global emas)."})
                try:
                    store_to_assign = Store.objects.get(pk=store_id)
                except Store.DoesNotExist:
                    raise serializers.ValidationError({"store_id": "Bunday do'kon topilmadi."})
            else:
                raise PermissionDenied("Kategoriya yaratish uchun do'konga biriktirilmagansiz.")
        serializer.save(store=store_to_assign)


class ProductViewSet(viewsets.ModelViewSet):
    """Mahsulotlar CRUD operatsiyalari va shtrix-kod funksiyalari"""
    queryset = Product.objects.select_related('category').filter(is_active=True) # Odatda faqat aktivlar
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticatedOrReadOnly] # Ko'rish hammaga, o'zgartirish adminlarga
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'barcode', 'description', 'category__name']
    ordering_fields = ['name', 'price_usd', 'price_uzs', 'created_at', 'updated_at']

    def get_queryset(self):
        user = self.request.user
        store_filter = Q()
        if user.is_superuser:
             # Superuser query param orqali filtrlay olsin yoki hamma narsani ko'rsin
             query_store_id = self.request.query_params.get('store_id')
             if query_store_id:
                 store_filter = Q(store_id=query_store_id)
             else:
                  return Product.objects.select_related('category', 'store').all() # Hamma narsa
        elif hasattr(user, 'profile') and user.profile.store:
             store_filter = Q(store=user.profile.store)
        else:
             return Product.objects.none()

        # is_active filtri (oldin yozilgan logikani saqlab qolish)
        queryset = Product.objects.select_related('category', 'store').filter(store_filter)
        is_active_param = self.request.query_params.get('is_active')
        if is_active_param is not None:
             is_active = is_active_param.lower() == 'true'
             queryset = queryset.filter(is_active=is_active)
        elif not user.is_staff: # Oddiy userlar faqat aktivlarni ko'radi
             queryset = queryset.filter(is_active=True)

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        store_to_assign = None
        if hasattr(user, 'profile') and user.profile.store:
             store_to_assign = user.profile.store
        elif user.is_superuser:
             store_id = self.request.data.get('store') # Serializerda 'category' bilan adashmaslik uchun
             if not store_id: raise serializers.ValidationError({"store": "Mahsulot qaysi do'konga tegishli ekanligi ko'rsatilmagan."})
             try: store_to_assign = Store.objects.get(pk=store_id)
             except Store.DoesNotExist: raise serializers.ValidationError({"store": "Bunday do'kon topilmadi."})
        else:
             raise PermissionDenied("Mahsulot yaratish uchun do'konga biriktirilmagansiz.")
        serializer.save(store=store_to_assign)


    def get_permissions(self):
         # Yaratish, yangilash, o'chirish uchun Admin ruxsati kerak
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'generate_barcode', 'barcode_data']:
            return [permissions.IsAdminUser()] # Yoki IsAdminRole
        return [permissions.IsAuthenticatedOrReadOnly()]

    @action(detail=False, methods=['post'], url_path='generate-barcode')
    def generate_barcode(self, request):
        """Yangi unikal shtrix-kod raqamini generatsiya qiladi (saqlamaydi)."""
        barcode_number = generate_unique_barcode_number()
        return Response({"barcode": barcode_number}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='barcode-data')
    def barcode_data(self, request, pk=None):
        """Mahsulot uchun shtrix-kod ma'lumotlarini (rasm bilan) qaytaradi."""
        product = self.get_object()
        if not product.barcode:
            return Response({"error": "Mahsulot uchun shtrix-kod mavjud emas."}, status=status.HTTP_404_NOT_FOUND)

        barcode_image_base64 = generate_barcode_image(product.barcode)

        if not barcode_image_base64:
            return Response({"error": "Shtrix-kod rasmini generatsiya qilib bo'lmadi."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        data_for_serializer = {
            "name": product.name,
            "price_uzs": product.price_uzs,
            "barcode_image_base64": barcode_image_base64,
            "barcode_number": product.barcode
        }
        serializer = BarcodeDataSerializer(instance=data_for_serializer)
        return Response(serializer.data)

    # Mahsulot yaratish/tahrirlashda narxni qayta hisoblash (modelda bor, lekin bu yerda ham tekshirish mumkin)
    # def perform_create(self, serializer):
    #     # Agar kerak bo'lsa, bu yerda qo'shimcha logika
    #     serializer.save()

    # def perform_update(self, serializer):
    #     # Agar kerak bo'lsa, bu yerda qo'shimcha logika
    #     serializer.save()