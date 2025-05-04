# smart_pos_project/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="Smart POS API",
      default_version='v1',
      description="Telefon, aksessuar va gadjetlar do'koni uchun API",
      # terms_of_service="...",
      contact=openapi.Contact(email="contact@example.com"), # O'zgartiring
      # license=openapi.License(name="..."),
   ),
   public=True, # Hamma dokumentatsiyani ko'ra olsin
   permission_classes=(permissions.AllowAny,), # Ruxsat tekshirish shart emas
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # API uchun asosiy yo'llar
    path('api/auth/', include('users.urls')), # Autentifikatsiya   # Foydalanuvchilarni boshqarish
    path('api/', include('products.urls')),  # Qo'shildi
    path('api/settings/', include('settings_app.urls')),
    path('api/inventory/', include('inventory.urls')),
    path('api/', include('sales.urls')),
    path('api/installments/', include('installments.urls')),
    path('api/reports/', include('reports.urls')),


    # API Dokumentatsiyasi uchun URLs
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)