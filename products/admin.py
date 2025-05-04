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
    list_display = ('name', 'description')
    search_fields = ('name',)
    # list_filter dan store olib tashlandi (agar bo'lsa)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'barcode', 'price_usd', 'price_uzs', 'is_active', 'updated_at')
    list_filter = ('category', 'is_active') # store filtri olib tashlandi
    search_fields = ('name', 'barcode', 'description')
    list_editable = ('is_active', 'price_usd')
    readonly_fields = ('price_uzs', 'created_at', 'updated_at', 'purchase_price_uzs') # purchase_price_uzs qo'shildi
    autocomplete_fields = ('category',)