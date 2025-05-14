# inventory/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    InventoryListView, LowStockListView,
    InventoryOperationView, InventoryHistoryListView, SupplierViewSet, PurchaseOrderViewSet
)

router = DefaultRouter()

router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'purchase-orders', PurchaseOrderViewSet, basename='purchase-order')

# Barcha endpointlar /api/inventory/ prefiksi bilan boshlanadi
urlpatterns = [
    path('', InventoryListView.as_view(), name='inventory-list'),
    path('low-stock/', LowStockListView.as_view(), name='inventory-low-stock'),
    path('history/', InventoryHistoryListView.as_view(), name='inventory-history'),
    # Amaliyotlar uchun alohida endpointlar
    path('add/', InventoryOperationView.as_view(), name='inventory-add'),
    path('remove/', InventoryOperationView.as_view(), name='inventory-remove'),
    path('transfer/', InventoryOperationView.as_view(), name='inventory-transfer'),

    path('', include(router.urls)),
]