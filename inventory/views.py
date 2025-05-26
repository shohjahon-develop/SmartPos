# inventory/views.py
from decimal import Decimal

from django.db import transaction
from rest_framework import generics, status, filters, permissions, serializers, exceptions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import F, Q # Q import qilindi

# Modellarni import qilish
from .models import ProductStock, InventoryOperation, PurchaseOrder, Supplier
from products.models import Product, Category, Kassa

# Serializerlarni import qilish
from .serializers import (
    ProductStockSerializer, InventoryOperationSerializer,
    InventoryAddSerializer, InventoryRemoveSerializer, InventoryTransferSerializer, PurchaseOrderDetailSerializer,
    ReceivePurchaseItemSerializer, PurchaseOrderCreateSerializer, PurchaseOrderListSerializer, SupplierSerializer
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
        .filter(
        quantity__lte=F('minimum_stock_level'),
        product__category__is_accessory_category=True  # YANGI FILTR
    ) \
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


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAdminUser]  # Yoki Omborchi/Admin
    search_fields = ['name', 'phone_number', 'contact_person']


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.select_related('supplier', 'created_by').prefetch_related('items__product',
                                                                                               'items__target_kassa').all()
    permission_classes = [permissions.IsAdminUser]  # Yoki Omborchi/Admin
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['supplier', 'status', 'payment_status', 'currency_choices', 'order_date']
    search_fields = ['id', 'supplier__name', 'items__product__name', 'notes']
    ordering_fields = ['order_date', 'total_amount', 'status']

    def get_serializer_class(self):
        if self.action == 'list':
            return PurchaseOrderListSerializer
        elif self.action == 'create':
            return PurchaseOrderCreateSerializer
        # retrieve, update, partial_update uchun Detail
        return PurchaseOrderDetailSerializer

    def perform_create(self, serializer):
        # created_by avtomatik o'rnatiladi (serializer.create da contextdan olinadi)
        serializer.save()  # user ni bu yerda uzatish shart emas, contextdan oladi

    # Mahsulotlarni qabul qilish uchun action
    @action(detail=True, methods=['post'], url_path='receive-items')
    def receive_items(self, request, pk=None):
        purchase_order = self.get_object()
        # Bu action bir nechta itemni bir vaqtda qabul qilish uchun o'zgartirilishi mumkin
        # Hozircha bitta item qabul qiladi deb faraz qilamiz (ReceivePurchaseItemSerializer bittaga mo'ljallangan)
        # Yoki ReceivePurchaseItemSerializer(many=True) ishlatish kerak

        # Agar bitta item qabul qilinsa:
        serializer = ReceivePurchaseItemSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            try:
                # Serializer.save() PurchaseOrderItem ni qaytaradi
                serializer.save(user=request.user)  # Amaliyotni bajargan user
                return Response(PurchaseOrderDetailSerializer(purchase_order, context={'request': request}).data,
                                status=status.HTTP_200_OK)
            except serializers.ValidationError as e:
                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"error": f"Mahsulot qabul qilishda xatolik: {str(e)}"},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Xarid uchun to'lov qilish actioni (soddalashtirilgan)
    @action(detail=True, methods=['post'], url_path='make-payment')
    def make_payment_for_purchase(self, request, pk=None):
        order = self.get_object()
        amount_str = request.data.get('amount')
        if not amount_str:
            return Response({"error": "To'lov summasi ('amount') kiritilmagan."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount_to_pay = Decimal(amount_str)
            if amount_to_pay <= 0:
                raise ValueError("To'lov summasi 0 dan katta bo'lishi kerak.")
        except (ValueError, TypeError):
            return Response({"error": "Noto'g'ri summa formati."}, status=status.HTTP_400_BAD_REQUEST)

        if amount_to_pay > order.remaining_amount_to_pay:
            # Xatolik berish yoki faqat qoldiqni to'lash
            # amount_to_pay = order.remaining_amount_to_pay
            return Response({
                                "error": f"To'lov summasi qoldiqdan ({order.remaining_amount_to_pay} {order.currency}) oshmasligi kerak."},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            order.amount_paid += amount_to_pay
            order.update_payment_status()  # Avtomatik PAID/PARTIALLY_PAID
            order.save()
            # Bu yerda KassaTransaction (CHIQIM) yaratish logikasi bo'lishi kerak
            # Masalan:
            # KassaTransaction.objects.create(kassa=..., amount=amount_to_pay, transaction_type=KassaTransaction.TransactionType.CASH_OUT, user=request.user, comment=f"Xarid #{order.id} uchun to'lov")

        return Response(PurchaseOrderDetailSerializer(order, context={'request': request}).data,
                        status=status.HTTP_200_OK)