# users/views.py
from django.contrib.auth.models import User
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import PermissionDenied # Bu kerak bo'lmay qolishi mumkin

# Modellarni import qilish
from .models import Role, UserProfile # Store kerak emas
# Serializerlarni import qilish
from .serializers import (RegisterSerializer, UserSerializer, RoleSerializer,
                          UserUpdateSerializer, MyTokenObtainPairSerializer, AdminUserCreateSerializer)
# Permissionlarni import qilish (hozircha standart)
# from .permissions import IsAdminRole # Yoki boshqa rollar

# Registratsiya View (O'zgarishsiz qoladi, chunki u store ga bog'liq emas edi)
@swagger_auto_schema(request_body=RegisterSerializer)
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,) # Hamma ro'yxatdan o'ta oladi
    serializer_class = RegisterSerializer

    # Javobni UserSerializer orqali formatlash
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Javobni UserSerializer orqali qaytaramiz (profile bilan)
        user_data = UserSerializer(user, context=self.get_serializer_context()).data
        headers = self.get_success_headers(serializer.data)
        return Response(user_data, status=status.HTTP_201_CREATED, headers=headers)



class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

# Rollarni boshqarish ViewSet (Faqat adminlar uchun)
class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAdminUser] # Faqat Django adminlari
    search_fields = ['name'] # Qidiruv qo'shildi


# Foydalanuvchilarni (Xodimlarni) boshqarish ViewSet

class UserViewSet(viewsets.ModelViewSet):
    """Foydalanuvchilarni (Xodimlarni) boshqarish"""
    # is_superuser filterini olib tashlaymiz, chunki superuser tushunchasi kerak emas
    queryset = User.objects.select_related('profile__role').all().order_by('username')
    permission_classes = [permissions.IsAdminUser] # Faqat adminlar boshqaradi (hozircha)
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['username', 'email', 'profile__full_name', 'profile__phone_number']
    # store filtri olib tashlandi
    filterset_fields = ['profile__role', 'is_active']
    ordering_fields = ['username', 'profile__full_name', 'date_joined']

    @swagger_auto_schema(request_body=AdminUserCreateSerializer)

    def get_serializer_class(self):
        if self.action == 'create':
            return AdminUserCreateSerializer  # <<<--- YANGI SERIALIZERNI QAYTARADI
        elif self.action in ['update', 'partial_update']:
            # Tahrirlashda is_staff ni ham o'zgartirish uchun UserUpdateSerializer ga qo'shdik
            return UserUpdateSerializer
        return UserSerializer  # list, retrieve, destroy uchun

    def create(self, request, *args, **kwargs):
        # Yaratish uchun AdminUserCreateSerializer ni ishlatamiz
        create_serializer = self.get_serializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)
        # Yaratilgan User obyektini olamiz
        user_instance = create_serializer.save()  # AdminUserCreateSerializer.create() User ni qaytaradi

        # Javobni UserSerializer (chiqish uchun mo'ljallangan) yordamida tayyorlaymiz
        response_serializer = UserSerializer(user_instance, context=self.get_serializer_context())
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    # perform_create endi kerak emas, chunki create ni to'liq override qildik
    # def perform_create(self, serializer):
    #     serializer.save()



    # perform_create, perform_update, perform_destroy dan store va is_superuser tekshiruvlari olib tashlandi
    # Standard ModelViewSet logikasi ishlashi mumkin

    # Agar adminlar bir-birini o'zgartira/o'chira olmasligi kerak bo'lsa,
    # perform_update va perform_destroy ni override qilish kerak.
    # def perform_update(self, serializer):
    #     if serializer.instance == self.request.user: # O'zini o'zi tahrirlash
    #         serializer.save()
    #     elif self.request.user.is_staff: # Boshqa admin/staff tahrirlayapti
    #         # Qo'shimcha tekshiruvlar (masalan, superuserni o'zgartirmaslik)
    #         # if not serializer.instance.is_superuser: serializer.save() ...
    #         serializer.save()
    #     else: raise PermissionDenied("...")

    # def perform_destroy(self, instance):
    #      if instance == self.request.user: raise PermissionDenied("O'zingizni o'chira olmaysiz.")
    #      if instance.is_superuser: raise PermissionDenied("Superuserni o'chira olmaysiz.")
    #      # Boshqa tekshiruvlar
    #      instance.delete()


# Superadmin uchun ViewSetlar (SuperadminStoreViewSet, SuperadminSubscriptionPlanViewSet) o'chirildi