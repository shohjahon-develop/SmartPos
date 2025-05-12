# sales/admin.py
from django.contrib import admin
from .models import Customer, Sale, SaleItem

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone_number', 'email', 'created_at')
    search_fields = ('full_name', 'phone_number', 'email')
    readonly_fields = ('created_at',)


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    # Endi price_at_sale_usd va price_at_sale_uzs ni ko'rsatamiz
    readonly_fields = ('product', 'quantity', 'price_at_sale_usd', 'price_at_sale_uzs', 'quantity_returned')
    extra = 0
    can_delete = False
    # Ko'rinadigan maydonlarni yangilash
    fields = ('product', 'quantity', 'price_at_sale_uzs', 'price_at_sale_usd', 'quantity_returned')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer',
        'seller',
        'kassa',
        'payment_type',
        'currency',  # YANGI: Sotuv valyutasini ko'rsatish
        'total_amount_currency',  # YANGI: Sotuv summasini ko'rsatish
        'status',
        'created_at'
    )
    list_filter = ('status', 'payment_type', 'kassa', 'currency', 'created_at', 'seller')  # currency qo'shildi
    search_fields = ('id', 'customer__full_name', 'customer__phone_number', 'seller__username')

    # readonly_fields ni yangi maydonlarga moslashtiramiz
    # Odatda, hisoblangan yoki avtomatik o'rnatiladigan maydonlar readonly bo'ladi
    readonly_fields = (
        'seller',  # Odatda avtomatik (yoki tanlanadi)
        'customer',  # Tanlanadi
        'kassa',  # Tanlanadi
        'currency',  # Yangi sotuvda tanlanadi, keyin o'zgarmasligi mumkin
        'total_amount_currency',  # Avtomatik hisoblanadi
        'amount_paid_currency',  # Avtomatik hisoblanadi yoki boshlang'ich to'lov
        'created_at',
        # Agar SaleReturn bog'liqligi bo'lsa, uni ham readonly qilish mumkin
        # 'sale_return_info' (maxsus metod orqali)
    )
    inlines = [SaleItemInline]
    list_select_related = ('customer', 'seller', 'kassa')

    # Admin panelida sotuv yaratish/o'chirishni taqiqlash (bu o'zgarishsiz)
    def has_add_permission(self, request):
        # Agar admin panelidan sotuv yaratishga ruxsat bermoqchi bo'lsangiz, True qiling
        # Lekin bu holda currency, total_amount_currency, amount_paid_currency
        # maydonlarini formaga qo'shish va logikani to'g'rilash kerak.
        # Odatda sotuvlar API yoki POS orqali yaratiladi.
        return False

        # Agar tahrirlash formasida ham yangi maydonlarni ko'rsatmoqchi bo'lsangiz,
    # fieldsets ni ishlatishingiz mumkin:
    # fieldsets = (
    #     (None, {
    #         'fields': ('seller', 'customer', 'kassa', 'payment_type', 'status')
    #     }),
    #     ('Summa va Valyuta', {
    #         'fields': ('currency', 'total_amount_currency', 'amount_paid_currency')
    #     }),
    #     ('Muhim Sanalar', {
    #         'fields': ('created_at',),
    #         'classes': ('collapse',) # Yashirish mumkin bo'lgan bo'lim
    #     }),
    # )