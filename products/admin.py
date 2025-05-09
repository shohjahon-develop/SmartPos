# products/admin.py
from django.contrib import admin
from .models import Kassa, Category, Product

@admin.register(Kassa)
class KassaAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'is_active')
    list_filter = ('is_active',) # store filtri olib tashlandi
    search_fields = ('name', 'location')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'barcode_prefix', 'description') # barcode_prefix qo'shildi
    search_fields = ('name', 'barcode_prefix')
    list_editable = ('barcode_prefix',) # Admin panelidan o'zgartirish imkoniyati

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'barcode', 'price_usd', 'price_uzs', 'is_active', 'updated_at')
    list_filter = ('category', 'is_active') # store filtri olib tashlandi
    search_fields = ('name', 'barcode', 'description')
    list_editable = (
    'is_active', 'price_usd', 'price_uzs', 'purchase_price_usd', 'purchase_price_uzs')  # Narxlar tahrirlanadigan bo'ldi
    readonly_fields = ('created_at', 'updated_at')  # price_uzs olib tashlandi
    autocomplete_fields = ('category',)