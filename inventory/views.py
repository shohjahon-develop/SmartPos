# inventory/views.py
from rest_framework import generics, status, filters, permissions, serializers, exceptions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import F, Q # Q import qilindi

# Modellarni import qilish
from .models import ProductStock, InventoryOperation
from products.models import Product, Category, Kassa

# Serializerlarni import qilish
from .serializers import (
    ProductStockSerializer, InventoryOperationSerializer,
    InventoryAddSerializer, InventoryRemoveSerializer, InventoryTransferSerializer
)
# Permissions
# from users.permissions import IsStorekeeper

class InventoryListView(generics.ListAPIView):
    """Ombordagi mahsulot qoldiqlarini ko'rish"""
    # store filtri olib tashlandi
    queryset = ProductStock.objects.select_related('product__category', 'kassa').all().order_by('kassa__name', 'product__name')
    serializer_class = ProductStockSerializer
    permission_classes = [permissions.IsAuthenticated] # Yoki IsStorekeeper/IsAdmin
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    # store filtri olib tashlandi
    filterset_fields = ['kassa', 'product__category', 'product__is_active']
    search_fields = ['product__name', 'product__barcode', 'kassa__name']
    ordering_fields = ['kassa__name', 'product__name', 'quantity']


class LowStockListView(generics.ListAPIView):
    """Miqdori minimal darajadan past bo'lgan mahsulotlar"""
    # store filtri olib tashlandi
    queryset = ProductStock.objects.select_related('product__category', 'kassa') \
                              .filter(quantity__lte=F('minimum_stock_level')) \
                              .order_by('kassa__name', 'product__name')
    serializer_class = ProductStockSerializer
    permission_classes = [permissions.IsAuthenticated] # Yoki IsStorekeeper/IsAdmin
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['kassa'] # store filtri olib tashlandi


class InventoryOperationView(generics.GenericAPIView):
    """Ombor amaliyotlarini bajarish (qo'shish, chiqarish, ko'chirish)"""
    permission_classes = [permissions.IsAdminUser] # Yoki IsStorekeeper/IsAdmin

    # get_serializer_class (o'zgarishsiz)
    def get_serializer_class(self):
         is_swagger_fake_view = getattr(self, 'swagger_fake_view', False)
         operation_type = None
         if not is_swagger_fake_view and hasattr(self, 'request') and self.request:
             try: operation_type = self.request.path.strip('/').split('/')[-1]
             except: pass

         if operation_type == 'add': return InventoryAddSerializer
         elif operation_type == 'remove': return InventoryRemoveSerializer
         elif operation_type == 'transfer': return InventoryTransferSerializer
         else:
             if is_swagger_fake_view: return InventoryAddSerializer # Swagger uchun default
             else: raise exceptions.NotFound(detail="Noto'g'ri ombor amaliyoti URL manzili.")

    # post metodidan store bilan bog'liq logikalar olib tashlandi
    def post(self, request, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                # Permission tekshiruvlari endi serializer yoki view permission_classes da
                result_data = serializer.save(user=request.user)
                return Response(result_data, status=status.HTTP_200_OK)
            # except PermissionDenied as e: # Agar serializerdan kelsa
            #      return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
            except serializers.ValidationError as e:
                 return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                print(f"Inventory operation error: {e}")
                return Response({"error": "Amaliyotni bajarishda ichki xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InventoryHistoryListView(generics.ListAPIView):
    """Ombor amaliyotlari tarixi"""
    # store filtri olib tashlandi
    queryset = InventoryOperation.objects.select_related(
        'product', 'user__profile', 'kassa', 'related_operation__product'
    ).all().order_by('-timestamp')
    serializer_class = InventoryOperationSerializer
    permission_classes = [permissions.IsAuthenticated] # Yoki IsStorekeeper/IsAdmin
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    # store filtri olib tashlandi
    filterset_fields = {
        'timestamp': ['date', 'date__gte', 'date__lte'],
        'product': ['exact'],
        'user': ['exact'],
        'kassa': ['exact'],
        'operation_type': ['exact', 'in'],
    }
    search_fields = ['product__name', 'user__username', 'comment', 'kassa__name']
    ordering_fields = ['timestamp', 'product__name']