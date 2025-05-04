# users/views.py
from django.contrib.auth.models import User
from rest_framework import generics, viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import PermissionDenied # Bu kerak bo'lmay qolishi mumkin

# Modellarni import qilish
from .models import Role, UserProfile # Store kerak emas
# Serializerlarni import qilish
from .serializers import (RegisterSerializer, UserSerializer, RoleSerializer,
                          UserUpdateSerializer, MyTokenObtainPairSerializer)
# Permissionlarni import qilish (hozircha standart)
# from .permissions import IsAdminRole # Yoki boshqa rollar

# Registratsiya View (O'zgarishsiz qoladi, chunki u store ga bog'liq emas edi)
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


# Login View (Store ma'lumotlari olib tashlangan)
# class CustomTokenObtainPairView(TokenObtainPairView):
#     def post(self, request, *args, **kwargs):
#         response = super().post(request, *args, **kwargs)
#         if response.status_code == 200:
#             user = None
#             try:
#                 # Token payloadidan user ID ni olish
#                 user_id = response.data.payload['user_id']
#                 user = User.objects.select_related('profile__role').get(id=user_id) # Profilni ham olish
#
#                 user_role = None
#                 user_full_name = user.get_full_name()
#
#                 if hasattr(user, 'profile'):
#                     profile = user.profile
#                     user_full_name = profile.full_name if profile.full_name else user_full_name
#                     if profile.role:
#                         user_role = profile.role.name
#
#                 user_info = {
#                     'id': user.id,
#                     'username': user.username,
#                     'full_name': user_full_name,
#                     'role': user_role,
#                     'is_superuser': user.is_superuser, # Superuser statusi qolishi mumkin
#                     # 'email': user.email, # Agar kerak bo'lsa
#                 }
#                 response.data['user'] = user_info
#
#             except Exception as e:
#                 print(f"WARNING: Could not add user info to token response for user: {user.username if user else 'UNKNOWN'} - {e}")
#                 # pass # Xatolik bo'lsa ham tokenlarni qaytarish uchun
#         return response
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

    def get_serializer_class(self):
         if self.action in ['update', 'partial_update']:
             return UserUpdateSerializer
         # create uchun RegisterSerializer ishlatilishi mumkin (agar admin yangi user qo'shsa)
         # Lekin registratsiya uchun alohida RegisterView bor
         # Bu yerda create ni cheklash mumkin
         # if self.action == 'create': return RegisterSerializer
         return UserSerializer # list, retrieve, destroy uchun

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