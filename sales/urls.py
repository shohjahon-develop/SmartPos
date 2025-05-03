# sales/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerViewSet, SaleViewSet, PosProductListView

router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'sales', SaleViewSet, basename='sale')

# Endpointlar /api/ prefiksi bilan boshlanadi
urlpatterns = [
    path('', include(router.urls)),
    path('pos/products/', PosProductListView.as_view(), name='pos-products'),
]