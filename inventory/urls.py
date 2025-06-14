# inventory/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    LowStockListView,  # Bu alohida qolishi mumkin, chunki u faqat aksessuarlar uchun edi
    InventoryOperationView,
    InventoryHistoryListView,
    SupplierViewSet,
    PurchaseOrderViewSet,
    ProductStockViewSet  # YANGI IMPORT QILINGAN VIEWSET
)

router = DefaultRouter()

# Mavjud router yozuvlari
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'purchase-orders', PurchaseOrderViewSet, basename='purchase-order')

# YANGI QO'SHILGAN ROUTER YOZUVI
# Bu /api/inventory/product-stocks/ endpointini yaratadi
# Bu orqali ProductStock uchun GET (list, retrieve), DELETE amallari bajariladi
# (PUT, PATCH metodlari ViewSetda o'chirilgan)
router.register(r'product-stocks', ProductStockViewSet, basename='product-stock')

urlpatterns = [
    # Maxsus endpointlar (routerga kirmaydiganlar)
    path('low-stock/', LowStockListView.as_view(), name='inventory-low-stock'),
    path('history/', InventoryHistoryListView.as_view(), name='inventory-history'),

    # Ombor amaliyotlari uchun alohida endpointlar (bular o'zgarishsiz)
    path('add/', InventoryOperationView.as_view(), name='inventory-add'),  # Ombordan kirim qilish
    path('remove/', InventoryOperationView.as_view(), name='inventory-remove'),  # Ombordan hisobdan chiqarish
    path('transfer/', InventoryOperationView.as_view(), name='inventory-transfer'),  # Ombordan ko'chirish

    # Router tomonidan generatsiya qilingan URLlar (yuqoridagi registerlarni o'z ichiga oladi)
    path('', include(router.urls)),
]