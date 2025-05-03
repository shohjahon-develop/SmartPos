# products/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import KassaViewSet, CategoryViewSet, ProductViewSet

router = DefaultRouter()
router.register(r'kassa', KassaViewSet, basename='kassa')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')

urlpatterns = [
    path('', include(router.urls)),
    # Boshqa maxsus endpointlar shu yerga qo'shilishi mumkin
]