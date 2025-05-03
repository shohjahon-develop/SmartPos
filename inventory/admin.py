# inventory/admin.py
from django.contrib import admin
from .models import ProductStock, InventoryOperation

@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    list_display = ('product', 'kassa', 'quantity', 'minimum_stock_level', 'is_low_stock')
    list_filter = ('kassa', 'product__category')
    search_fields = ('product__name', 'kassa__name', 'product__barcode')
    list_select_related = ('product', 'kassa', 'product__category') # Optimallashtirish
    # Qoldiqni admin paneldan o'zgartirish xavfli bo'lishi mumkin,
    # faqat amaliyotlar orqali qilish tavsiya etiladi.
    # list_editable = ('quantity', 'minimum_stock_level') # Ehtiyot bo'ling!
    readonly_fields = ('is_low_stock',)

@admin.register(InventoryOperation)
class InventoryOperationAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'product', 'kassa', 'quantity', 'operation_type', 'user', 'comment_short')
    list_filter = ('operation_type', 'kassa', 'timestamp', 'user')
    search_fields = ('product__name', 'user__username', 'comment', 'product__barcode')
    list_select_related = ('product', 'kassa', 'user')
    readonly_fields = ('timestamp', 'related_operation') # Odatda bu maydonlar o'zgartirilmaydi
    autocomplete_fields = ('product', 'user', 'kassa') # Tanlashni osonlashtirish

    @admin.display(description='Izoh (qisqa)')
    def comment_short(self, obj):
        if obj.comment:
            return (obj.comment[:50] + '...') if len(obj.comment) > 50 else obj.comment
        return '-'