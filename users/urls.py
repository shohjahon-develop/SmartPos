# users/urls_users.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import *

router = DefaultRouter()
router.register(r'roles', RoleViewSet, basename='role') # Qo'shildi
router.register(r'users', UserViewSet, basename='user') # UserViewSet qo'shildi
router.register(r'sa/stores', SuperadminStoreViewSet, basename='sa-store')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('', include(router.urls)),
]