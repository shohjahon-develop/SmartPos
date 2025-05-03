# settings_app/admin.py
from django.contrib import admin
from .models import StoreSettings, CurrencyRate

@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    # Singleton model bo'lgani uchun list_display shart emas
    # Faqat tahrirlash oynasini ko'rsatish
    def has_add_permission(self, request): # Yangi qo'shishni taqiqlash
        return False
    def has_delete_permission(self, request, obj=None): # O'chirishni taqiqlash
        return False

@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ('usd_to_uzs_rate', 'last_updated')
    readonly_fields = ('last_updated',) # Avtomatik yangilanadi
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False