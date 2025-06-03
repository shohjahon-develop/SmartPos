# sales/views.py
from django.db.models.functions import Coalesce
from rest_framework import viewsets, generics, status, filters, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import OuterRef, Subquery, IntegerField, Value, Count  # Value qo'shildi

# Modellarni import qilish
from .models import Customer, Sale, SaleItem, Kassa # Store kerak emas
from products.models import Product # Category kerak emas
from inventory.models import ProductStock

# Serializerlarni import qilish
from .serializers import *
# Permissionlar
# from users.permissions import IsSeller, IsAdminRole

class CustomerViewSet(viewsets.ModelViewSet):
    """Mijozlar CRUD operatsiyalari"""
    queryset = Customer.objects.all().order_by('-created_at') # store filtri olib tashlandi
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated] # Yoki IsSeller/IsAdmin
    search_fields = ['full_name', 'phone_number', 'email']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter] # DjangoFilterBackend kerak emas
    # filterset_fields olib tashlandi
    ordering_fields = ['full_name', 'created_at']

    # perform_create dan store ni belgilash olib tashlandi


class CurrencyExchangeView(generics.GenericAPIView):
    serializer_class = CurrencyExchangeSerializer
    permission_classes = [permissions.IsAdminUser] # Yoki maxsus rol

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            # Serializer.save() KassaTransactionSerializer formatidagi ikkita tranzaksiya qaytaradi
            result_data = serializer.save(user=request.user)
            return Response(result_data, status=status.HTTP_200_OK)
        except serializers.ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Umumiy xatoliklar uchun
            print(f"Currency exchange error: {e}")
            import traceback
            traceback.print_exc()
            return Response({"error": "Valyuta ayirboshlashda ichki xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SaleViewSet(viewsets.ModelViewSet):
    """Sotuvlarni ko'rish va yangi sotuv yaratish"""
    # store filtri olib tashlandi
    queryset = Sale.objects.select_related(
        'seller__profile', 'customer', 'kassa' # store kerak emas
    ).prefetch_related('items__product').all().order_by('-created_at')
    permission_classes = [permissions.IsAuthenticated] # Yoki IsSeller/IsAdmin
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    # store filtri olib tashlandi
    filterset_fields = {
        'created_at': ['date', 'date__gte', 'date__lte'],
        'payment_type': ['exact', 'in'],
        'seller': ['exact'],
        'customer': ['exact'],
        'kassa': ['exact'],
        'status': ['exact', 'in'],
    }
    search_fields = ['id', 'customer__full_name', 'customer__phone_number', 'items__product__name']
    ordering_fields = ['created_at', 'total_amount_uzs', 'status']

    def get_queryset(self):
        # Asosiy queryset ni olish
        queryset = Sale.objects.select_related(
            'seller__profile', 'customer', 'kassa'
        ).prefetch_related(
            'items__product'  # prefetch_related muhim
        )

        # items_count ni annotate qilish
        queryset = queryset.annotate(
            items_count_annotated=Count('items')  # items - bu Sale modelidagi related_name
        )
        return queryset.order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'list':
            return SaleListSerializer
        elif self.action == 'create':
            return SaleCreateSerializer  # Yaratish uchun INPUT serializeri
        # retrieve va boshqa holatlar uchun OUTPUT serializeri
        # (return_sale uchun ham mos kelishi mumkin)
        return SaleDetailSerializer

    def perform_create(self, serializer):
        # Bu standart metod, user ni avtomatik bog'laydi
        # serializer.save() bu yerda Sale obyektini qaytaradi
        serializer.save(user=self.request.user)

        # Standart create ni override qilib, javobni to'g'ri formatlaymiz

    def create(self, request, *args, **kwargs):
        # Yaratish uchun INPUT serializerini ishlatamiz
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # perform_create obyektni yaratadi, lekin qaytarmaydi
        # serializer.save() ni chaqirib, yaratilgan Sale obyektini olamiz
        # Yoki perform_create ni chaqirib, keyin instance ni olish:
        self.perform_create(serializer)  # Bu user ni ham bog'laydi
        sale_instance = serializer.instance  # Yaratilgan Sale obyekti

        # Javobni OUTPUT serializeri (SaleDetailSerializer) yordamida tayyorlaymiz
        response_serializer = SaleDetailSerializer(sale_instance, context=self.get_serializer_context())
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    # update, partial_update, destroy metodlari (o'zgarishsiz)
    def update(self, request, *args, **kwargs):
        return Response({"detail": "Metod 'PUT' ruxsat etilmagan."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    def partial_update(self, request, *args, **kwargs):
         return Response({"detail": "Metod 'PATCH' ruxsat etilmagan."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    def destroy(self, request, *args, **kwargs):
         return Response({"detail": "Metod 'DELETE' ruxsat etilmagan."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=True, methods=['post'], url_path='return',
            permission_classes=[permissions.IsAuthenticated])  # Ruxsatni moslang
    def return_sale(self, request, pk=None):
        """Ushbu sotuvdan mahsulotlarni qaytarish"""
        sale = self.get_object()  # Sotuvni olish

        # Serializerga request, data va context (sale) ni berish
        serializer = SaleReturnSerializer(
            data=request.data,
            context={'sale_instance': sale, 'request': request}  # request ni ham berish muhim (user uchun)
        )
        if serializer.is_valid():
            try:
                # Serializer.create() yangilangan sotuv detalini qaytaradi
                updated_sale_data = serializer.save(user=request.user)  # User ni uzatish
                return Response(updated_sale_data, status=status.HTTP_200_OK)
            except Exception as e:
                # Xatolikni loglash va javob qaytarish
                print(f"Error processing sale return for sale {pk}: {e}")
                # Agar ValidationError bo'lsa, uni qaytarish mumkin
                if isinstance(e, serializers.ValidationError):
                    return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
                return Response({"error": "Qaytarish jarayonida xatolik yuz berdi."},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PosProductListView(generics.ListAPIView):
    serializer_class = PosProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category']
    search_fields = ['name', 'barcode']

    def get_queryset(self):
        print("DEBUG: PosProductListView.get_queryset() chaqirildi.")  # Metod boshlandi
        queryset = Product.objects.select_related('category').filter(is_active=True)
        print(f"DEBUG: Dastlabki aktiv mahsulotlar soni: {queryset.count()}")

        kassa_id = self.request.query_params.get('kassa_id')
        print(f"DEBUG: So'ralgan kassa_id: {kassa_id}")

        if kassa_id:
            try:
                kassa = Kassa.objects.get(pk=kassa_id, is_active=True)
                print(f"DEBUG: Topilgan kassa: {kassa.name} (ID: {kassa.id})")

                stock_subquery = ProductStock.objects.filter(
                    product=OuterRef('pk'),
                    kassa=kassa
                ).values('quantity')[:1]

                queryset = queryset.annotate(
                    quantity_in_stock_sub=Coalesce(Subquery(stock_subquery, output_field=IntegerField()), Value(0))
                )

                # Annotate qilingan qiymatlarni tekshirish uchun:
                # Bu qismni vaqtincha aktivlashtirib, har bir mahsulot uchun qoldiqni ko'ring
                # print("DEBUG: Annotate qilingan qoldiqlar (filtrdan oldin):")
                # for item in list(queryset): # list() bazaga so'rov yuboradi
                #     print(f"  Mahsulot ID {item.id} ({item.name}): quantity_in_stock_sub = {getattr(item, 'quantity_in_stock_sub', 'Yo`q')}")

                # Faqat qoldig'i 0 dan katta bo'lganlarni filtrlash
                queryset_before_filter_count = queryset.count()  # Filtrdan oldingi soni
                queryset = queryset.filter(quantity_in_stock_sub__gt=0)
                print(
                    f"DEBUG: `quantity_in_stock_sub__gt=0` filtridan OLDIN soni: {queryset_before_filter_count}, KEYIN soni: {queryset.count()}")

            except Kassa.DoesNotExist:
                print(f"DEBUG XATO: Kassa ID={kassa_id} topilmadi (is_active=True sharti bilan).")
                return queryset.none()
            except ValueError:
                print(f"DEBUG XATO: Kassa ID='{kassa_id}' noto'g'ri formatda.")
                return queryset.none()
            except Exception as e:
                print(f"DEBUG: get_queryset ichida kutilmagan xatolik: {e}")
                import traceback
                traceback.print_exc()
                return queryset.none()
        else:
            print("DEBUG: kassa_id berilmadi. Barcha mahsulotlar uchun quantity_in_stock_sub=0 o'rnatiladi.")
            queryset = queryset.annotate(quantity_in_stock_sub=Value(0, output_field=IntegerField()))
            # Agar kassa_id berilmaganda ham qoldig'i borlarni ko'rsatmoqchi bo'lsak, bu yerda ham filtr kerak
            # Masalan, birinchi aktiv kassa uchun qoldiqni olish:
            # first_active_kassa = Kassa.objects.filter(is_active=True).first()
            # if first_active_kassa:
            #     print(f"DEBUG: kassa_id berilmadi, birinchi aktiv kassa ({first_active_kassa.name}) ishlatiladi.")
            #     stock_subquery = ProductStock.objects.filter(product=OuterRef('pk'), kassa=first_active_kassa).values('quantity')[:1]
            #     queryset = queryset.annotate(quantity_in_stock_sub=Coalesce(Subquery(stock_subquery, output_field=IntegerField()), Value(0)))
            #     queryset = queryset.filter(quantity_in_stock_sub__gt=0) # Va filtr qo'llash
            # else:
            #     print("DEBUG: kassa_id berilmadi va aktiv kassa ham topilmadi.")
            #     queryset = queryset.annotate(quantity_in_stock_sub=Value(0, output_field=IntegerField()))

        return queryset.order_by('category__name', 'name')

    def list(self, request, *args, **kwargs):  # list metodi avvalgidek
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        results = []
        items_to_serialize = page if page is not None else queryset

        # Vaqtincha debug uchun
        # print(f"DEBUG (list metodi): Serializatsiyadan oldin items_to_serialize:")
        # for item_debug in list(items_to_serialize): # Bazaga so'rov
        #      print(f"  Item ID: {item_debug.id}, Name: {item_debug.name}, quantity_in_stock_sub: {getattr(item_debug, 'quantity_in_stock_sub', 'Yo`q')}")

        for item in items_to_serialize:
            data = self.get_serializer(item).data
            data['quantity_in_stock'] = getattr(item, 'quantity_in_stock_sub', 0)
            results.append(data)

        if page is not None:
            return self.get_paginated_response(results)
        return Response(results)


class CashInView(generics.CreateAPIView):
    """Kassaga naqd pul kirim qilish"""
    serializer_class = CashInSerializer
    permission_classes = [permissions.IsAdminUser] # Yoki maxsus rol (Kassir, Admin)

    def perform_create(self, serializer):
        # Yaratilgan KassaTransaction ni user bilan bog'lash
        instance = serializer.save(user=self.request.user)
        # Javobni KassaTransactionSerializer orqali formatlash (ixtiyoriy)
        # self.response_serializer = KassaTransactionSerializer(instance) # Javobni formatlash uchun

    # Agar javobni formatlamoqchi bo'lsangiz, create metodini override qiling:
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer) # Bu yerda instance qaytadi
        response_serializer = KassaTransactionSerializer(instance) # Javob uchun serializer
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class CashOutView(generics.CreateAPIView):
    """Kassadan naqd pul chiqim qilish (xarajat)"""
    serializer_class = CashOutSerializer
    permission_classes = [permissions.IsAdminUser] # Yoki maxsus rol

    def perform_create(self, serializer):
        instance = serializer.save(user=self.request.user)
        # self.response_serializer = KassaTransactionSerializer(instance)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        response_serializer = KassaTransactionSerializer(instance)
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)