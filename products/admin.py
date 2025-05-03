# products/admin.py
from django.contrib import admin
from .models import Kassa, Category, Product

@admin.register(Kassa)
class KassaAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'location')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'barcode', 'price_usd', 'price_uzs', 'is_active', 'updated_at')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'barcode', 'description')
    list_editable = ('is_active', 'price_usd') # Narxni shu yerdan o'zgartirish qulay
    readonly_fields = ('price_uzs', 'created_at', 'updated_at') # Avtomatik hisoblanadi/o'rnatiladi
    autocomplete_fields = ('category',) # Kategoriya tanlashni osonlashtirish
    # Narxni o'zgartirganda avtomatik qayta hisoblash uchun save_model ni override qilish mumkin
    # def save_model(self, request, obj, form, change):
    #     obj.calculate_price_uzs() # Narxni yangilash
    #     super().save_model(request, obj, form, change)