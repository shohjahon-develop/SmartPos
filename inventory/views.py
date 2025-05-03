# inventory/views.py
from rest_framework import generics, status, filters, permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import F, Q  # F object for comparing model fields

from . import serializers
from .models import ProductStock, InventoryOperation
from .serializers import (
    ProductStockSerializer, InventoryOperationSerializer,
    InventoryAddSerializer, InventoryRemoveSerializer, InventoryTransferSerializer
)
from products.models import Product, Category, Kassa # Filtrlar uchun

# --- Ruxsatlar (agar kerak bo'lsa, users/permissions.py da yaratish mumkin) ---
# class IsStorekeeper(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return request.user.is_authenticated and request.user.profile.role.name == 'Omborchi'

# --- Viewlar ---

class InventoryListView(generics.ListAPIView):
    """Ombordagi mahsulot qoldiqlarini ko'rish"""
    serializer_class = ProductStockSerializer
    permission_classes = [permissions.IsAuthenticated] # Hozircha hamma autentifikatsiyadan o'tganlar
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # Kassa va Category allaqachon store ga bog'liq
    filterset_fields = ['kassa', 'product__category', 'product__is_active']
    # Agar superuser store bo'yicha filtrlamoqchi bo'lsa:
    # filterset_fields = ['kassa__store', 'kassa', 'product__category', 'product__is_active']
    search_fields = ['product__name', 'product__barcode', 'kassa__name']
    ordering_fields = ['kassa__name', 'product__name', 'quantity']

    def get_queryset(self):
        user = self.request.user
        queryset = ProductStock.objects.select_related('product__category', 'kassa__store',
                                                       'product__store')  # store lar qo'shildi

        if user.is_superuser:
            store_id = self.request.query_params.get('store_id')
            if store_id:
                # Kassa yoki Product orqali filtrlash
                queryset = queryset.filter(Q(kassa__store_id=store_id) | Q(product__store_id=store_id))
            # Hamma qoldiqlarni qaytarish
        elif hasattr(user, 'profile') and user.profile.store:
            # Foydalanuvchi do'konidagi kassalar yoki mahsulotlar qoldig'i
            queryset = queryset.filter(Q(kassa__store=user.profile.store) | Q(product__store=user.profile.store))
        else:
            queryset = queryset.none()
        return queryset.distinct().order_by('kassa__name', 'product__name')  # distinct() qo'shildi


class LowStockListView(generics.ListAPIView):
    """Miqdori minimal darajadan past bo'lgan mahsulotlar"""
    serializer_class = ProductStockSerializer
    permission_classes = [permissions.IsAuthenticated] # Odatda Admin/Omborchi
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['kassa', 'kassa__store']

    def get_queryset(self):
        user = self.request.user
        queryset = ProductStock.objects.select_related('product__category', 'kassa__store', 'product__store') \
            .filter(quantity__lte=F('minimum_stock_level'))

        if user.is_superuser:
            store_id = self.request.query_params.get('store_id')
            if store_id:
                queryset = queryset.filter(Q(kassa__store_id=store_id) | Q(product__store_id=store_id))
            # Hamma kam qoldiqlar
        elif hasattr(user, 'profile') and user.profile.store:
            queryset = queryset.filter(Q(kassa__store=user.profile.store) | Q(product__store=user.profile.store))
        else:
            queryset = queryset.none()

        return queryset.distinct().order_by('kassa__name', 'product__name')


class InventoryOperationView(generics.GenericAPIView):
    """Ombor amaliyotlarini bajarish (qo'shish, chiqarish, ko'chirish)"""
    # Ruxsat: Masalan, faqat Admin yoki Omborchi
    permission_classes = [permissions.IsAdminUser] # Yoki IsStorekeeper

    # Qaysi serializer ishlatilishini URL ga qarab aniqlaymiz
    def get_serializer_class(self):
        # URL pathini olish (masalan, '/api/inventory/add/')
        operation_type = self.request.path.strip('/').split('/')[-1]
        if operation_type == 'add':
            return InventoryAddSerializer
        elif operation_type == 'remove':
            return InventoryRemoveSerializer
        elif operation_type == 'transfer':
            return InventoryTransferSerializer
        return None # Boshqa holatda None qaytaradi

    def check_object_permissions(self, request, obj):
        # Bu yerda obj emas, balki serializer.validated_data dagi
        # kassa yoki mahsulot userning do'koniga tegishli ekanligini tekshirish kerak.
        # Buni serializerning validate() metodida qilish qulayroq.
        pass

    def post(self, request, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        if not serializer_class:
            return Response({"error": "Noto'g'ri amaliyot turi."}, status=status.HTTP_400_BAD_REQUEST)

        # Serializerga request ni uzatish (store ni tekshirish uchun)
        serializer = serializer_class(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                # Perform permission check inside save or before calling save
                # (We will add validation in serializers below)
                result_data = serializer.save(user=request.user)
                return Response(result_data, status=status.HTTP_200_OK)
            except PermissionDenied as e:
                return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
            except serializers.ValidationError as e:
                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                print(f"Inventory operation error: {e}")
                return Response({"error": "Amaliyotni bajarishda ichki xatolik."},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class InventoryHistoryListView(generics.ListAPIView):
    """Ombor amaliyotlari tarixi"""
    serializer_class = InventoryOperationSerializer
    permission_classes = [permissions.IsAuthenticated] # Admin/Omborchi
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    # Filtrlar: sana oralig'i, mahsulot, foydalanuvchi, kassa, amaliyot turi
    filterset_fields = {
        'timestamp': ['date', 'date__gte', 'date__lte'], # YYYY-MM-DD formatida
        'product': ['exact'],
        'kassa__store': ['exact'],
        'user': ['exact'],
        'kassa': ['exact'],
        'operation_type': ['exact', 'in'], # 'in' bir nechta turni tanlash uchun
    }
    search_fields = ['product__name', 'user__username', 'comment', 'kassa__name']
    ordering_fields = ['timestamp', 'product__name'] # Default: -timestamp (modelda)

    def get_queryset(self):
        user = self.request.user
        # Kassa yoki Product orqali store ni olamiz
        queryset = InventoryOperation.objects.select_related(
            'product__store', 'user__profile', 'kassa__store', 'related_operation__product'
        )

        if user.is_superuser:
            store_id = self.request.query_params.get('store_id')
            if store_id:
                queryset = queryset.filter(kassa__store_id=store_id)
            # Hamma tarix
        elif hasattr(user, 'profile') and user.profile.store:
            queryset = queryset.filter(kassa__store=user.profile.store)
        else:
            queryset = queryset.none()
        return queryset.order_by('-timestamp')  # Default ordering