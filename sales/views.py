# sales/views.py
from django.db.models import OuterRef, Subquery, IntegerField, Value
from rest_framework import viewsets, generics, status, filters, permissions, serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from users.models import Store
from .models import Customer, Sale, SaleItem
from .serializers import (
    CustomerSerializer, SaleListSerializer, SaleDetailSerializer, SaleCreateSerializer, PosProductSerializer
)
from inventory.models import ProductStock
from products.models import Product, Category, Kassa
from products.serializers import ProductSerializer as POSProductSerializer # Maxsus nom
# from users.permissions import IsSeller, IsAdminRole # Maxsus ruxsatlar

class CustomerViewSet(viewsets.ModelViewSet):
    """Mijozlar CRUD operatsiyalari"""
    queryset = Customer.objects.all().order_by('-created_at')
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated] # Yoki IsSeller/IsAdmin
    search_fields = ['full_name', 'phone_number', 'email']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend] # DjangoFilterBackend qo'shildi
    filterset_fields = ['store'] # Superuser uchun filtr
    ordering_fields = ['full_name', 'created_at']

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            # Superuser query param orqali filtrlay olsin
            store_id = self.request.query_params.get('store_id')
            if store_id:
                return Customer.objects.filter(store_id=store_id).order_by('-created_at')
            return Customer.objects.all().order_by('-created_at') # Hamma mijozlar
        if hasattr(user, 'profile') and user.profile.store:
            return Customer.objects.filter(store=user.profile.store).order_by('-created_at')
        return Customer.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        store_to_assign = None
        if hasattr(user, 'profile') and user.profile.store:
            store_to_assign = user.profile.store
        elif user.is_superuser:
            store_id = self.request.data.get('store_id')
            if not store_id: raise serializers.ValidationError({"store_id": "Mijoz qaysi do'konga tegishli ekanligi ko'rsatilmagan."})
            try: store_to_assign = Store.objects.get(pk=store_id)
            except Store.DoesNotExist: raise serializers.ValidationError({"store_id": "Bunday do'kon topilmadi."})
        else:
            raise PermissionDenied("Mijoz yaratish uchun do'konga biriktirilmagansiz.")
        # Telefon raqam unikalligini do'kon ichida tekshirish (serializerda qilish yaxshiroq)
        serializer.save(store=store_to_assign)


class SaleViewSet(viewsets.ModelViewSet):
    """Sotuvlarni ko'rish va yangi sotuv yaratish"""
    permission_classes = [permissions.IsAuthenticated] # Kimlar ko'ra/yarata oladi?
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
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
        user = self.request.user
        queryset = Sale.objects.select_related(
            'seller__profile', 'customer', 'kassa', 'store' # store ni qo'shdik
        ).prefetch_related(
            'items__product'
        ) # .all() ni olib tashlaymiz

        if user.is_superuser:
            store_id = self.request.query_params.get('store_id')
            if store_id:
                 queryset = queryset.filter(store_id=store_id)
            # Store ID berilmasa, hamma sotuvlar qaytariladi
        elif hasattr(user, 'profile') and user.profile.store:
            queryset = queryset.filter(store=user.profile.store)
            # Agar oddiy sotuvchi faqat o'zinikini ko'rishi kerak bo'lsa:
            # if user.profile.role.name == 'Sotuvchi': # Yoki boshqa tekshiruv
            #     queryset = queryset.filter(seller=user)
        else:
            queryset = queryset.none()

        return queryset.order_by('-created_at') # Order by ni qo'shish

    def perform_create(self, serializer):
        # SaleCreateSerializer allaqachon user va kassa orqali store ni biladi
        # Faqat superuser holatini ko'rish kerak
        user = self.request.user
        store_to_assign = None
        if hasattr(user, 'profile') and user.profile.store:
            store_to_assign = user.profile.store
        elif user.is_superuser:
             # Sotuv yaratishda superuser qaysi do'kon nomidan ishlayotganini bilish kerak
             # Bu odatda kassa orqali aniqlanadi
             kassa_id = self.request.data.get('kassa_id')
             if not kassa_id: raise serializers.ValidationError({"kassa_id": "Kassa tanlanmagan."})
             try:
                 kassa = Kassa.objects.select_related('store').get(pk=kassa_id)
                 store_to_assign = kassa.store
             except Kassa.DoesNotExist: raise serializers.ValidationError({"kassa_id": "Bunday kassa topilmadi."})
        else:
             raise PermissionDenied("Sotuv yaratish uchun do'konga biriktirilmagansiz.")

        # Serializerga user va store ni uzatish
        # Serializer.save() ichida store ni ishlatish logikasi bo'lishi kerak
        serializer.save(user=user, store=store_to_assign) # store ni uzatish

    # Sotuvni tahrirlash (PUT/PATCH) va o'chirish (DELETE) odatda cheklanadi.
    # Buning o'rniga qaytarish (RETURN) kabi maxsus actionlar ishlatiladi (keyingi bosqichda).
    def update(self, request, *args, **kwargs):
        return Response({"detail": "Metod 'PUT' ruxsat etilmagan."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        return Response({"detail": "Metod 'PATCH' ruxsat etilmagan."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def destroy(self, request, *args, **kwargs):
         return Response({"detail": "Metod 'DELETE' ruxsat etilmagan."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


class PosProductListView(generics.ListAPIView):
    """POS (Kassa) ekrani uchun mahsulotlar ro'yxati (qoldiq bilan)"""
    serializer_class = PosProductSerializer # Serializerni o'zgartirdik
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category']
    search_fields = ['name', 'barcode']

    def get_queryset(self):
        user = self.request.user
        store = None
        if hasattr(user, 'profile') and user.profile.store:
            store = user.profile.store
        elif user.is_superuser:
             # Superuser uchun store_id yoki kassa_id kerak
             kassa_id = self.request.query_params.get('kassa_id')
             store_id = self.request.query_params.get('store_id')
             if kassa_id:
                  try: store = Kassa.objects.get(pk=kassa_id).store
                  except Kassa.DoesNotExist: return Product.objects.none()
             elif store_id:
                  try: store = Store.objects.get(pk=store_id)
                  except Store.DoesNotExist: return Product.objects.none()
             else:
                  # Agar ikkalasi ham berilmasa, qaysi do'kon mahsulotlarini ko'rsatish kerak?
                  # Hozircha xatolik yoki birinchi do'kon
                  return Product.objects.none() # Yoki xatolik qaytarish
        else:
             return Product.objects.none() # Do'konga biriktirilmagan

        # Faqat shu do'konning aktiv mahsulotlari
        queryset = Product.objects.select_related('category') \
                                .filter(store=store, is_active=True)

        # Kassa bo'yicha filtrlash va qoldiqni olish
        kassa_id = self.request.query_params.get('kassa_id')
        if kassa_id:
            try:
                # Kassa shu do'kongami?
                kassa = Kassa.objects.get(pk=kassa_id, store=store)

                # Subquery yordamida har bir mahsulot uchun shu kassadagi qoldiqni olish
                stock_subquery = ProductStock.objects.filter(
                    product=OuterRef('pk'),
                    kassa=kassa
                ).values('quantity')[:1] # Faqat bitta qiymat (quantity)

                # Qoldiqni annotate qilish va faqat qoldig'i > 0 bo'lganlarni filterlash
                queryset = queryset.annotate(
                    quantity_in_stock_sub=Subquery(stock_subquery, output_field=IntegerField())
                ).filter(quantity_in_stock_sub__gt=0)

            except (Kassa.DoesNotExist, ValueError):
                return queryset.none() # Kassa topilmasa yoki ID noto'g'ri bo'lsa
        else:
            # Agar kassa berilmasa, qoldiqni ko'rsatmaymiz yoki umumiy qoldiq?
            # Hozircha qoldiqsiz qaytaramiz (yoki xatolik berish ham mumkin)
            # Yoki barcha kassalardagi umumiy qoldiqni annotate qilish mumkin (murakkabroq)
             queryset = queryset.annotate(quantity_in_stock_sub=Value(None, output_field=IntegerField())) # Qoldiq noma'lum
             # Yoki umuman qoldig'i bor mahsulotlarni filterlash (avvalgi kod kabi)
             # product_ids_in_stock = ProductStock.objects.filter(
             #     product__store=store, quantity__gt=0
             # ).values_list('product_id', flat=True).distinct()
             # queryset = queryset.filter(id__in=product_ids_in_stock)


        return queryset.order_by('category__name', 'name')

    def list(self, request, *args, **kwargs):
        """List natijasiga qoldiqni qo'shib beradi"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        # Annotate qilingan qiymatni serializerga o'tkazish uchun
        # data ni qayta ishlashimiz kerak bo'lishi mumkin, yoki serializer to'g'ri ishlashi kerak
        # Hozirgi serializerda 'quantity_in_stock' read_only, u data da bo'lishi kerak
        # Subquery nomi 'quantity_in_stock_sub' edi, buni moslashtirish kerak

        results = []
        if page is not None:
             # Serializerga har bir obyektni alohida uzatib, contextga qoldiqni berish
             # Bu samarasizroq, lekin Subquery ishlamasa yoki murakkab bo'lsa yaxshi
             # serializer = self.get_serializer(page, many=True)

             # Yoki Subquery natijasini to'g'ri nomga o'tkazish
             for item in page:
                  data = self.get_serializer(item).data
                  # Subquery natijasini olish ('quantity_in_stock_sub' edi)
                  # Agar subquery ishlatmasak, bu yerda qoldiqni alohida so'rov bilan olish kerak
                  if hasattr(item, 'quantity_in_stock_sub') and item.quantity_in_stock_sub is not None:
                       data['quantity_in_stock'] = item.quantity_in_stock_sub
                  else:
                       # Agar subquery ishlatilmagan yoki None bo'lsa
                       # Qoldiqni alohida so'rov bilan olish (SAMARASIZ!)
                       # kassa_id = request.query_params.get('kassa_id')
                       # if kassa_id:
                       #     try:
                       #         stock = ProductStock.objects.get(product_id=item.id, kassa_id=kassa_id)
                       #         data['quantity_in_stock'] = stock.quantity
                       #     except ProductStock.DoesNotExist:
                       #         data['quantity_in_stock'] = 0
                       # else:
                            data['quantity_in_stock'] = 0 # Agar kassa berilmasa, 0 deb ko'rsatamiz
                  results.append(data)

             return self.get_paginated_response(results)

        # Agar pagination bo'lmasa (kam ehtimol)
        serializer = self.get_serializer(queryset, many=True)
        # Bu holatda ham qoldiqni qo'shish kerak
        results = []
        for i, item in enumerate(queryset):
             data = serializer.data[i]
             if hasattr(item, 'quantity_in_stock_sub') and item.quantity_in_stock_sub is not None:
                  data['quantity_in_stock'] = item.quantity_in_stock_sub
             else:
                  data['quantity_in_stock'] = 0
             results.append(data)
        return Response(results)