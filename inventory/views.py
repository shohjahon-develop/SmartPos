# inventory/views.py
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction, IntegrityError
from rest_framework import generics, status, filters, permissions, serializers, exceptions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import F, Q, Sum, Value, IntegerField # Sum, Value, IntegerField qo'shildi
from django.db.models.functions import Coalesce # Coalesce import qilindi
from rest_framework import filters as drf_filters

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


# class ProductStockViewSet(viewsets.ModelViewSet):
#     """
#     Ombordagi mahsulot qoldiqlarini (ProductStock) ko'rish va o'chirish.
#     O'chirish faqat ma'lum shartlar bajarilganda amalga oshiriladi.
#     Qoldiqni tahrirlashga ruxsat berilmaydi (operatsiyalar orqali o'zgaradi).
#     """
#     queryset = ProductStock.objects.select_related(
#         'product__category', 'kassa'
#     ).all().order_by('kassa__name', 'product__name')
#     serializer_class = ProductStockSerializer
#     permission_classes = [permissions.IsAdminUser]  # Faqat adminlar uchun
#     filter_backends = [DjangoFilterBackend, drf_filters.SearchFilter, drf_filters.OrderingFilter]
#     filterset_fields = {
#         'kassa': ['exact'],
#         'product': ['exact'],
#         'product__category': ['exact'],
#         'product__is_active': ['exact'],
#         'quantity': ['exact', 'gte', 'lte', 'gt', 'lt'],
#         'is_low_stock': ['exact'],  # Property bo'yicha filtr uchun alohida filter class kerak bo'lishi mumkin
#         # Yoki querysetda annotate qilish kerak. Hozircha oddiyroq.
#     }
#     search_fields = ['product__name', 'product__barcode', 'kassa__name']
#     ordering_fields = ['kassa__name', 'product__name', 'quantity', 'minimum_stock_level']
#
#     def get_queryset(self):
#         queryset = super().get_queryset()
#         # is_low_stock bo'yicha filtrni qo'lda qo'shamiz, chunki u property
#         # Yoki django-filterda FilterSet class yaratib, BooleanFilter bilan qilish mumkin.
#         is_low = self.request.query_params.get('is_low_stock')
#         if is_low is not None:
#             if is_low.lower() == 'true':
#                 # Bu logikani yanada optimallashtirish mumkin,
#                 # hozircha har bir obyekt uchun propertyni hisoblaydi.
#                 # Yaxshiroq yo'l: F() expression bilan solishtirish
#                 # queryset = queryset.filter(quantity__lt=F('minimum_stock_level'))
#                 # Lekin bu xuddi LowStockListView dek bo'lib qoladi.
#                 # Agar generic filtr kerak bo'lsa, FilterSet class yaxshiroq.
#                 # Hozircha, soddalik uchun, agar is_low_stock so'ralsa, LowStockListView logikasini takrorlaymiz
#                 queryset = queryset.filter(
#                     quantity__lt=F('minimum_stock_level'))  # lt o'rniga lte (LowStockListView dagi kabi)
#             elif is_low.lower() == 'false':
#                 queryset = queryset.filter(quantity__gte=F('minimum_stock_level'))
#         return queryset
#
#     # Qoldiqni va minimal miqdorni API orqali to'g'ridan-to'g'ri o'zgartirishga ruxsat bermaymiz.
#     # Bular ombor operatsiyalari yoki maxsus sozlamalar orqali o'zgarishi kerak.
#     def update(self, request, *args, **kwargs):
#         return Response(
#             {"detail": "Metod 'PUT' ruxsat etilmagan. Qoldiqni ombor operatsiyalari orqali o'zgartiring."},
#             status=status.HTTP_405_METHOD_NOT_ALLOWED
#         )
#
#     def partial_update(self, request, *args, **kwargs):
#         # minimum_stock_level ni o'zgartirish uchun alohida action qilish mumkin
#         instance = self.get_object()
#         # Faqat minimum_stock_level ni o'zgartirishga ruxsat beramiz (masalan)
#         allowed_fields_to_update = {'minimum_stock_level'}
#
#         if not set(request.data.keys()).issubset(allowed_fields_to_update):
#             return Response(
#                 {"detail": f"Faqat {', '.join(allowed_fields_to_update)} maydon(lar)ini o'zgartirish mumkin."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#
#         # Agar faqat minimum_stock_level kelayotgan bo'lsa:
#         serializer = self.get_serializer(instance, data=request.data, partial=True)
#         serializer.is_valid(raise_exception=True)
#
#         # quantity maydoni o'zgartirilmayotganini tekshirish
#         if 'quantity' in serializer.validated_data and serializer.validated_data['quantity'] != instance.quantity:
#             return Response(
#                 {"quantity": ["Qoldiqni bu yerda o'zgartirib bo'lmaydi. Ombor operatsiyalaridan foydalaning."]},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#
#         self.perform_update(serializer)
#         return Response(serializer.data)
#
#     @transaction.atomic
#     def destroy(self, request, *args, **kwargs):
#         instance = self.get_object()  # ProductStock instansi
#
#         if instance.quantity == 0:
#             # Agar qoldiq 0 bo'lsa, darhol o'chiramiz
#             # O'chirishdan oldin bog'liq INITIAL operatsiyalarni topib, ularni ham tozalash mumkin
#             # (lekin bu Product o'chirilganda CASCADE bilan bo'lishi kerak edi)
#             # Hozircha, faqat ProductStock o'chiriladi.
#             initial_operations_for_this_stock = InventoryOperation.objects.filter(
#                 product=instance.product,
#                 kassa=instance.kassa,
#                 operation_type=InventoryOperation.OperationType.INITIAL
#             )
#             # Agar bu ProductStock uchun faqat INITIAL operatsiyalar bo'lsa va ularning
#             # yig'indisi 0 ga teng bo'lsa (bu g'alati holat, lekin tekshirish mumkin)
#             # yoki ularni shunchaki log uchun olib, keyin ProductStockni o'chirish.
#             # Eng yaxshisi, bu yerda InventoryOperation ga tegmaslik.
#             # Chunki Product o'chirilganda ular PROTECT bilan qolishi kerak (agar Product o'chirilmasa).
#
#             self.perform_destroy(instance)
#             return Response(status=status.HTTP_204_NO_CONTENT)
#
#         # Agar qoldiq > 0 bo'lsa, operatsiyalar tarixini tekshiramiz
#         operations = InventoryOperation.objects.filter(
#             product=instance.product,
#             kassa=instance.kassa
#         ).order_by('timestamp')
#
#         # Faqat INITIAL turidagi operatsiyalar yig'indisi joriy qoldiqqa tengmi?
#         initial_ops_total_quantity = Decimal(0)
#         has_other_than_initial_ops = False
#
#         # Bu yerda product va kassa uchun barcha operatsiyalarni olamiz
#         # va ularning yig'indisi ProductStock.quantity ga tengligini tekshiramiz.
#         # Bu biroz murakkab, chunki har bir operatsiya (+/-) quantity ga ta'sir qiladi.
#         # Eng yaxshisi, faqat INITIAL operatsiyalar borligini tekshirish.
#
#         # Barcha operatsiyalar faqat INITIAL turidami?
#         non_initial_ops_count = operations.exclude(
#             operation_type=InventoryOperation.OperationType.INITIAL
#         ).filter(Q(quantity__gt=0) | Q(quantity__lt=0)).count()  # 0 bo'lmagan miqdorli operatsiyalar
#
#         if non_initial_ops_count == 0:
#             # Faqat INITIAL operatsiyalar mavjud (yoki hech qanday operatsiya yo'q, bu holat quantity=0 da tekshirilgan)
#             # Bu degani, qoldiq faqat ProductSerializer.create() dan kelgan.
#
#             # Teskari (bekor qiluvchi) InventoryOperation yaratamiz
#             # Bu operatsiya quantity ni manfiy qilib, joriy qoldiqni oladi
#             # va operation_type ni REMOVE (yoki maxsus tur) qiladi.
#             try:
#                 InventoryOperation.objects.create(
#                     product=instance.product,
#                     kassa=instance.kassa,
#                     user=request.user if request.user.is_authenticated else None,
#                     quantity=-instance.quantity,  # Joriy qoldiqni to'liq ayiramiz
#                     operation_type=InventoryOperation.OperationType.REMOVE,  # Hisobdan chiqarish
#                     comment=f"ProductStock ID {instance.id} ({instance.product.name} @ {instance.kassa.name}) o'chirilishi sababli boshlang'ich kirim(lar) bekor qilindi."
#                 )
#             except IntegrityError as e:  # Masalan, product yoki kassa PROTECT bilan o'chirilgan bo'lsa
#                 return Response(
#                     {"error": f"Ombor yozuvini bekor qilish operatsiyasini yaratishda xatolik: {str(e)}"},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
#
#             # ProductStock qoldig'ini 0 ga tushiramiz
#             # Bu aslida yuqoridagi operatsiya natijasida avtomatik bo'lishi kerak (agar signallar yoki boshqa mexanizm bo'lsa)
#             # Lekin xavfsizlik uchun qo'lda ham yangilaymiz
#             # instance.quantity = 0
#             # instance.save(update_fields=['quantity'])
#             # Yoki F() expression bilan:
#             ProductStock.objects.filter(pk=instance.pk).update(quantity=F('quantity') - instance.quantity)
#
#             instance.refresh_from_db()  # Bazadan yangilangan qiymatni olamiz
#             if instance.quantity != 0:
#                 # Agar qoldiq baribir 0 ga tushmagan bo'lsa (bu kutilmagan holat)
#                 return Response(
#                     {
#                         "error": "Boshlang'ich kirimni bekor qilishdan so'ng qoldiq 0 ga tushmadi. Ma'mur bilan bog'laning."},
#                     status=status.HTTP_500_INTERNAL_SERVER_ERROR
#                 )
#
#             # Endi ProductStock yozuvini o'chiramiz
#             self.perform_destroy(instance)
#             return Response(
#                 {"message": "Boshlang'ich xato kirim(lar) muvaffaqiyatli bekor qilindi va ombor yozuvi o'chirildi."},
#                 status=status.HTTP_204_NO_CONTENT
#             )
#         else:
#             # Agar INITIAL dan boshqa (ADD, SALE, REMOVE, TRANSFER) operatsiyalar bo'lsa
#             return Response(
#                 {"error": (
#                     f"'{instance.product.name}' @ '{instance.kassa.name}' yozuvini o'chirib bo'lmaydi. "
#                     f"Joriy qoldiq: {instance.quantity} dona. Bu yozuv bilan bog'liq qo'shimcha ombor operatsiyalari mavjud. "
#                     "Iltimos, avval mahsulot qoldig'ini ombor operatsiyalari orqali 0 (nol) ga tushiring."
#                 )},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

# class LowStockListView(generics.ListAPIView):
#     """Miqdori minimal darajadan past bo'lgan mahsulotlar"""
#     # store filtri olib tashlandi
#     queryset = ProductStock.objects.select_related('product__category', 'kassa') \
#         .filter(
#         quantity__lte=F('minimum_stock_level'),
#         product__category__is_accessory_category=True  # YANGI FILTR
#     ) \
#         .order_by('kassa__name', 'product__name')
#     serializer_class = ProductStockSerializer
#     permission_classes = [permissions.IsAuthenticated] # Yoki IsStorekeeper/IsAdmin
#     filter_backends = [DjangoFilterBackend]
#     filterset_fields = ['kassa'] # store filtri olib tashlandi
class ProductStockViewSet(viewsets.ModelViewSet):
    """
    Ombordagi mahsulot qoldiqlarini (ProductStock) ko'rish va o'chirish.
    """
    queryset = ProductStock.objects.select_related(
        'product__category', 'kassa'
    ).all().order_by('kassa__name', 'product__name')
    serializer_class = ProductStockSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, drf_filters.SearchFilter, drf_filters.OrderingFilter]

    # O'ZGARTIRILDI: filterset_fields dan 'is_low_stock' olib tashlandi
    filterset_fields = {
        'kassa': ['exact'],
        'product': ['exact'],
        'product__category': ['exact'],
        'product__is_active': ['exact'],
        'quantity': ['exact', 'gte', 'lte', 'gt', 'lt'],
        # 'is_low_stock': ['exact'], # OLIB TASHALDI
    }
    search_fields = ['product__name', 'product__barcode', 'kassa__name']
    ordering_fields = ['kassa__name', 'product__name', 'quantity', 'minimum_stock_level']

    # get_queryset metodini endi is_low_stock uchun maxsus filtrsiz qoldiramiz.
    # Agar is_low_stock bo'yicha filtr kerak bo'lsa, LowStockListView dan foydalanish mumkin
    # yoki bu yerga query_params orqali qo'lda qo'shish mumkin.
    def get_queryset(self):
        queryset = super().get_queryset()  # Asosiy querysetni oladi (filter_backends va filterset_fields ishlaydi)

        # Agar ?is_low_stock=true/false query parametri kelsa, uni qo'lda qayta ishlashimiz mumkin:
        is_low_param = self.request.query_params.get('is_low_stock')
        if is_low_param is not None:
            if is_low_param.lower() == 'true':
                queryset = queryset.filter(quantity__lt=F('minimum_stock_level'))  # is_low_stock propertysiga mos
            elif is_low_param.lower() == 'false':
                queryset = queryset.filter(quantity__gte=F('minimum_stock_level'))
        return queryset

    def update(self, request, *args, **kwargs):
        return Response({"detail": "Metod 'PUT' ruxsat etilmagan."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        allowed_fields_to_update = {'minimum_stock_level'}
        if not set(request.data.keys()).issubset(allowed_fields_to_update):
            return Response(
                {"detail": f"Faqat {', '.join(allowed_fields_to_update)} maydon(lar)ini o'zgartirish mumkin."},
                status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        if 'quantity' in serializer.validated_data and serializer.validated_data['quantity'] != instance.quantity:
            return Response({"quantity": ["Qoldiqni bu yerda o'zgartirib bo'lmaydi."]},
                            status=status.HTTP_400_BAD_REQUEST)

        self.perform_update(serializer)
        # Javobda is_low_stock ni ham ko'rsatish uchun (agar serializerda bo'lsa)
        # Yoki instance ni qayta o'qib, serializerga berish
        instance.refresh_from_db()
        return Response(self.get_serializer(instance).data)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()  # ProductStock instansi
        user_performing_action = request.user if request.user.is_authenticated else None
        if not user_performing_action:  # Agar IsAdminUser bo'lsa, bu holat bo'lmasligi kerak
            admin_user = User.objects.filter(is_superuser=True, is_active=True).first()
            user_performing_action = admin_user

        if instance.quantity == 0:
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)

        # Agar qoldiq > 0 bo'lsa
        operations = InventoryOperation.objects.filter(
            product=instance.product,
            kassa=instance.kassa
        ).order_by('timestamp')

        non_initial_ops_count = operations.exclude(
            operation_type=InventoryOperation.OperationType.INITIAL
        ).filter(Q(quantity__gt=0) | Q(quantity__lt=0)).count()

        if non_initial_ops_count == 0:
            # Faqat INITIAL operatsiyalar mavjud (yoki hech qanday, bu quantity=0 da tekshirilgan)
            # Bu "toza" boshlang'ich kirim(lar) holati
            try:
                InventoryOperation.objects.create(
                    product=instance.product, kassa=instance.kassa, user=user_performing_action,
                    quantity=-instance.quantity, operation_type=InventoryOperation.OperationType.REMOVE,
                    comment=f"ProductStock ID {instance.id} o'chirilishi sababli boshlang'ich kirim(lar) avtomatik bekor qilindi."
                )
                # ProductStock qoldig'ini 0 ga tushirish
                updated_rows = ProductStock.objects.filter(pk=instance.pk).update(
                    quantity=Value(0))  # To'g'ridan-to'g'ri 0 ga o'rnatish
                if updated_rows == 0: raise Exception("ProductStock qoldig'ini yangilab bo'lmadi.")

                instance.refresh_from_db()  # refresh_from_db o'rniga to'g'ridan to'g'ri o'chirish
                # if instance.quantity == 0: # Bu endi har doim true bo'lishi kerak
                self.perform_destroy(instance)
                return Response(
                    {"message": "Boshlang'ich kirim(lar) avtomatik bekor qilindi va ombor yozuvi o'chirildi."},
                    status=status.HTTP_204_NO_CONTENT
                )
                # else:
                #     transaction.set_rollback(True)
                #     return Response({"error": "Boshlang'ich kirimni bekor qilishda kutilmagan xatolik. Qoldiq 0 ga tushmadi."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            except Exception as e:
                transaction.set_rollback(True)
                return Response({"error": f"Ombor yozuvini o'chirishda xatolik (boshlang'ich): {str(e)}"},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            # Agar INITIAL dan boshqa operatsiyalar bo'lsa (TALABGA KO'RA O'ZGARTIRILGAN QISM)
            try:
                # 1. Qoldiqni 0 ga tushiruvchi REMOVE operatsiyasini avtomatik yaratamiz
                InventoryOperation.objects.create(
                    product=instance.product,
                    kassa=instance.kassa,
                    user=user_performing_action,
                    quantity=-instance.quantity,  # Joriy qoldiqni to'liq ayiramiz
                    operation_type=InventoryOperation.OperationType.REMOVE,
                    comment=f"ProductStock ID {instance.id} ({instance.product.name} @ {instance.kassa.name}) o'chirilishi uchun qoldiq avtomatik 0 ga tushirildi."
                )

                # 2. ProductStock qoldig'ini 0 ga tushiramiz
                updated_rows = ProductStock.objects.filter(pk=instance.pk).update(quantity=Value(0))
                if updated_rows == 0:
                    # Agar biror sabab bilan yangilanmasa (bu kutilmaydi, lekin xavfsizlik uchun)
                    # Odatda bu holatda yuqoridagi IntegrityError ga tushishi kerak agar kaskadli o'chirish bo'lsa
                    raise Exception("ProductStock qoldig'ini avtomatik 0 ga tushirib bo'lmadi.")

                # 3. Endi ProductStock yozuvini o'chiramiz
                self.perform_destroy(instance)
                return Response(
                    {
                        "message": f"Mahsulot qoldig'i ({instance.quantity} dona) avtomatik hisobdan chiqarildi va ombor yozuvi o'chirildi."},
                    status=status.HTTP_204_NO_CONTENT
                )
            except IntegrityError as e:
                # Agar InventoryOperation yaratishda yoki ProductStock o'chirishda PROTECT xatoligi bo'lsa
                transaction.set_rollback(True)
                return Response(
                    {
                        "error": f"Ombor yozuvini o'chirishda bog'liqlik xatosi: {str(e)}. Avval bog'liq yozuvlarni hal qiling."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                transaction.set_rollback(True)
                return Response(
                    {"error": f"Ombor yozuvini avtomatik tozalash va o'chirishda kutilmagan xatolik: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

class LowStockListView(generics.ListAPIView):
    serializer_class = ProductStockSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['kassa']
    def get_queryset(self):
        accessory_categories = Category.objects.filter(is_accessory_category=True)
        if not accessory_categories.exists(): return ProductStock.objects.none()
        queryset = ProductStock.objects.select_related('product__category', 'kassa') \
                                  .filter(quantity__lte=F('minimum_stock_level'), product__category__in=accessory_categories) \
                                  .order_by('kassa__name', 'product__name')
        return queryset



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