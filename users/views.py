# users/views.py
from django.contrib.auth.models import User
from django_filters import filters
from rest_framework import viewsets, permissions, generics, status, filters # <--- Mana shu import muhim
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, viewsets, permissions, status, serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from subscriptions.models import SubscriptionPlan
from subscriptions.serializers import SubscriptionPlanSerializer
from .models import Role, UserProfile, Store
from .permissions import IsSuperuser
from .serializers import RegisterSerializer, UserSerializer, RoleSerializer, UserUpdateSerializer, StoreListSerializer, \
    StoreUpdateSerializer, StoreCreateSerializer, StoreDetailSerializer


# Registratsiya View
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,) # Hamma ro'yxatdan o'ta oladi
    serializer_class = RegisterSerializer

    # Yaratilgan foydalanuvchi ma'lumotini qaytarish uchun (ixtiyoriy)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user_data = UserSerializer(user, context=self.get_serializer_context()).data
        headers = self.get_success_headers(serializer.data) # serializer.data o'rniga user_data?
        return Response(user_data, status=status.HTTP_201_CREATED, headers=headers)


# Login View (JWT token olish va qo'shimcha ma'lumot)
class CustomTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        # Token muvaffaqiyatli olinganda javobga user ma'lumotlarini qo'shish
        if response.status_code == 200:
            try:
                # `serializer.user` orqali foydalanuvchini olish xavfsizroq
                user = self.serializer_class.get_user_from_token(response.data['access'])
                # Yoki username orqali olish (hozirgidek)
                # user = User.objects.get(username=request.data['username'])

                store_info = None
                user_role = None
                user_full_name = user.get_full_name() # Standart User modelidan

                # UserProfile va Store ma'lumotlarini olishga harakat qilish
                if hasattr(user, 'profile'):
                     profile = user.profile
                     user_full_name = profile.full_name if profile.full_name else user_full_name # Profildagi ism ustunroq
                     if profile.role:
                         user_role = profile.role.name
                     if profile.store:
                         store = profile.store
                         store_info = {
                             'id': store.id,
                             'name': store.name,
                             'is_active': store.is_active,
                             # Balki obuna haqida qisqacha ma'lumot?
                             # 'plan': store.subscription_plan, # Agar ForeignKey bo'lsa, plan nomini olish kerak
                             # 'expiry_date': store.expiry_date.strftime('%Y-%m-%d') if store.expiry_date else None,
                         }

                # Agar Superuser bo'lsa, maxsus belgi qo'yish mumkin
                is_superuser = user.is_superuser

                user_info = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'full_name': user_full_name,
                    'role': user_role,
                    'store': store_info, # Store ma'lumoti qo'shildi
                    'is_superuser': is_superuser, # Superuser statusi
                    # Kerak bo'lsa boshqa ma'lumotlar
                }
                response.data['user'] = user_info # Mavjud 'user' kalitiga yozamiz

            # except User.DoesNotExist: # Agar username orqali olinsa
            #      pass # Foydalanuvchi topilmasa, oddiy token javobi qoladi
            except Exception as e:
                 # Xatolikni loglash muhim!
                 print(f"Error adding user/store info to token response: {e}")
                 # Javobga xatolik haqida ma'lumot qo'shmaslik yaxshiroq,
                 # chunki token allaqachon berilgan. Log qilish kifoya.
                 pass
        return response


# Rollarni boshqarish ViewSet (admin uchun)
class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAdminUser] # Faqat Django adminlariga ruxsat
    # Keyinchalik IsAdminRole permissionini yaratamiz


class UserViewSet(viewsets.ModelViewSet):
    """Xodimlarni (Foydalanuvchilarni) boshqarish"""
    serializer_class = UserSerializer # Ro'yxat va detal uchun
    permission_classes = [permissions.IsAdminUser] # Hozircha faqat Django adminlari
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['username', 'email', 'profile__full_name', 'profile__phone_number']
    filterset_fields = ['profile__role', 'is_active', 'profile__store'] # Store bo'yicha filtr
    ordering_fields = ['username', 'profile__full_name', 'date_joined']

    def get_queryset(self):
        user = self.request.user
        # Superuser hamma do'kon xodimlarini ko'ra oladi
        if user.is_superuser:
            return User.objects.select_related('profile__role', 'profile__store').all()
        # Do'kon admini faqat o'z do'koni xodimlarini ko'radi
        elif hasattr(user, 'profile') and user.profile.store:
            return User.objects.select_related('profile__role', 'profile__store').filter(profile__store=user.profile.store)
        # Boshqa holatlar (masalan, do'konga bog'lanmagan admin)
        return User.objects.none() # Yoki xatolik qaytarish

    def get_serializer_class(self):
         if self.action in ['update', 'partial_update']:
             return UserUpdateSerializer
         elif self.action == 'create':
             # Ro'yxatdan o'tish serializerini ishlatish yoki maxsus UserCreateSerializer yaratish
             # Hozircha RegisterSerializer ni ishlatamiz, lekin store ni o'tkazish kerak
             return RegisterSerializer # Yoki maxsus UserCreateSerializer
         return UserSerializer # list, retrieve, destroy uchun

    def perform_create(self, serializer):
        # Yaratilayotgan user qaysi do'konga tegishli ekanligini aniqlash
        request_user = self.request.user
        store = None
        if request_user.is_superuser:
            # Superadmin user yaratganda frontenddan store_id kelishi kerak
            store_id = self.request.data.get('store_id') # Frontend yuborishi kerak
            if not store_id:
                raise serializers.ValidationError({"store_id": "Superadmin uchun do'kon tanlanishi shart."})
            try:
                store = Store.objects.get(pk=store_id)
            except Store.DoesNotExist:
                raise serializers.ValidationError({"store_id": "Bunday do'kon mavjud emas."})
        elif hasattr(request_user, 'profile') and request_user.profile.store:
            # Do'kon admini faqat o'z do'koniga xodim qo'sha oladi
            store = request_user.profile.store
        else:
            raise PermissionDenied("Xodim qo'shish uchun siz do'konga biriktirilmagansiz.")

        # Role ni ham tekshirish mumkin (masalan, faqat 'Admin' rolidagilar qo'sha olsin)

        # Validatsiyadan o'tgan ma'lumotlarga store ni qo'shib save qilish
        serializer.save(store=store) # RegisterSerializer.create metodiga 'store' uzatiladi

    def perform_update(self, serializer):
         # Tahrirlanayotgan user joriy userning do'koniga tegishli ekanligini tekshirish
         # (get_queryset buni qisman ta'minlaydi, lekin qo'shimcha tekshiruv xavfsizroq)
         instance_to_update = self.get_object()
         request_user = self.request.user
         if not request_user.is_superuser:
             if not hasattr(request_user, 'profile') or instance_to_update.profile.store != request_user.profile.store:
                  raise PermissionDenied("Siz faqat o'z do'koningiz xodimlarini tahrirlay olasiz.")
         # Agar superadmin tahrirlayotgan bo'lsa, store ni o'zgartirish imkoniyatini ham qo'shish mumkin
         serializer.save()

    def perform_destroy(self, instance):
        # O'chirilayotgan user joriy userning do'koniga tegishli ekanligini tekshirish
        request_user = self.request.user
        if not request_user.is_superuser:
            if not hasattr(request_user, 'profile') or instance.profile.store != request_user.profile.store:
                 raise PermissionDenied("Siz faqat o'z do'koningiz xodimlarini o'chira olasiz.")
            if instance == request_user: # Admin o'zini o'chira olmaydi
                 raise PermissionDenied("Siz o'zingizni o'chira olmaysiz.")
        # Superuserni o'chirishni taqiqlash
        if instance.is_superuser:
             raise PermissionDenied("Superadminni o'chirib bo'lmaydi.")
        instance.delete()


# --- Superadmin uchun ViewSetlar ---

class SuperadminStoreViewSet(viewsets.ModelViewSet):
    """Do'konlarni boshqarish (Superadmin uchun)"""
    queryset = Store.objects.select_related('owner__profile', 'subscription_plan').all()
    permission_classes = [IsSuperuser] # Faqat Superadminlar

    def get_serializer_class(self):
        if self.action == 'list':
            return StoreListSerializer
        elif self.action == 'retrieve':
            return StoreDetailSerializer
        elif self.action == 'create':
            return StoreCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return StoreUpdateSerializer
        return StoreListSerializer # Default

    # create, update, destroy metodlarini override qilish shart emas,
    # chunki serializerlar asosiy logikani bajaradi.
    # Faqat qo'shimcha harakatlar kerak bo'lsa (masalan, email yuborish) override qilinadi.

    # Limitlarni tekshirish uchun annotate qo'shish mumkin (list actionida)
    # def get_queryset(self):
    #     qs = super().get_queryset()
    #     if self.action == 'list':
    #         qs = qs.annotate(
    #             users_count=Count('user_profiles', distinct=True),
    #             products_count=Count('products', distinct=True),
    #             # kassa_count=Count('kassas', distinct=True)
    #         )
    #     return qs

class SuperadminSubscriptionPlanViewSet(viewsets.ModelViewSet):
    """Obuna tariflarini boshqarish (Superadmin uchun)"""
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer # Endi bu nom aniqlangan
    permission_classes = [IsSuperuser]