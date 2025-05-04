# sales/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (CustomerViewSet, SaleViewSet, PosProductListView,
                  CashInView, CashOutView) # Yangi Viewlarni import qiling

router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'sales', SaleViewSet, basename='sale') # Bu /sales/{id}/return/ ni ham qamrab oladi

# Endpointlar /api/ prefiksi bilan boshlanadi
urlpatterns = [
    path('', include(router.urls)),
    path('pos/products/', PosProductListView.as_view(), name='pos-products'),
    # Yangi Kassa Amaliyotlari uchun URLlar
    path('kassa/cash-in/', CashInView.as_view(), name='kassa-cash-in'),
    path('kassa/cash-out/', CashOutView.as_view(), name='kassa-cash-out'),
    # Kassadagi barcha tranzaksiyalarni ko'rish uchun ListAPIView ham qo'shish mumkin
    # path('kassa/transactions/', KassaTransactionListView.as_view(), name='kassa-transactions'),
]