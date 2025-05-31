# # products/admin.py
# from django.contrib import admin
# from .models import Kassa, Category, Product
#
# @admin.register(Kassa)
# class KassaAdmin(admin.ModelAdmin):
#     list_display = ('name', 'location', 'is_active')
#     list_filter = ('is_active',) # store filtri olib tashlandi
#     search_fields = ('name', 'location')
#
# @admin.register(Category)
# class CategoryAdmin(admin.ModelAdmin):
#     list_display = ('name', 'barcode_prefix', 'description', 'is_accessory_category') # barcode_prefix qo'shildi
#     search_fields = ('name', 'barcode_prefix')
#     list_editable = ('barcode_prefix',) # Admin panelidan o'zgartirish imkoniyati
#
# @admin.register(Product)
# class ProductAdmin(admin.ModelAdmin):
#     list_display = ('name', 'category', 'barcode', 'price_usd', 'price_uzs','purchase_price_usd',
#         'purchase_price_uzs', 'is_active', 'updated_at')
#     list_filter = ('category', 'is_active') # store filtri olib tashlandi
#     search_fields = ('name', 'barcode', 'description')
#     list_editable = (
#     'is_active', 'price_usd', 'price_uzs', 'purchase_price_usd', 'purchase_price_uzs')  # Narxlar tahrirlanadigan bo'ldi
#     readonly_fields = ('created_at', 'updated_at')  # price_uzs olib tashlandi
#     autocomplete_fields = ('category',)

# products/admin.py
from django.contrib import admin
from .models import Kassa, Category, Product


@admin.register(Kassa)
class KassaAdmin(admin.ModelAdmin):
    # ... (o'zgarishsiz) ...
    list_display = ('name', 'location', 'is_active');
    list_filter = ('is_active',);
    search_fields = ('name', 'location')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # ... (o'zgarishsiz) ...
    list_display = ('name', 'barcode_prefix', 'is_accessory_category', 'description');
    search_fields = ('name', 'barcode_prefix');
    list_filter = ('is_accessory_category',);
    list_editable = ('barcode_prefix', 'is_accessory_category')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'category', 'barcode',
        'supplier_name_manual', 'supplier_phone_manual',  # YANGI MATNLI MAYDONLAR
        'price_usd', 'price_uzs', 'purchase_price_usd',
        'purchase_price_uzs', 'is_active', 'updated_at'
    )
    list_filter = ('category', 'is_active')  # supplier (ForeignKey) olib tashlandi
    search_fields = (
        'name', 'barcode', 'description',
        'supplier_name_manual', 'supplier_phone_manual'  # YANGI MATNLI MAYDONLAR
    )
    list_editable = (
        'is_active', 'price_usd', 'price_uzs', 'purchase_price_usd', 'purchase_price_uzs'
    )
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('category',)  # supplier (ForeignKey) olib tashlandi

    # Formada ko'rinadigan maydonlarni tartiblash (ixtiyoriy)
    fieldsets = (
        (None, {
            'fields': ('name', 'category', 'barcode', 'is_active')
        }),
        ('Yetkazib Beruvchi Ma\'lumotlari (Qo\'lda)', {  # YANGI BO'LIM
            'fields': ('supplier_name_manual', 'supplier_phone_manual'),
            'classes': ('collapse',),  # Boshida yopiq turishi uchun (ixtiyoriy)
        }),
        ('Narxlar va Sotib Olish', {
            'fields': ('price_uzs', 'price_usd', 'purchase_price_uzs', 'purchase_price_usd', 'purchase_date')
        }),
        ('Qo\'shimcha Ma\'lumotlar', {
            'fields': ('description', 'storage_capacity', 'color', 'series_region', 'battery_health',
                       'default_kassa_for_new_stock')
        }),
        ('Avtomatik Maydonlar', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )