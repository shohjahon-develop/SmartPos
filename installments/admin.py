# installments/admin.py
from django.contrib import admin
from .models import InstallmentPlan, InstallmentPayment, PaymentSchedule # PaymentSchedule ni import qiling
from django.utils.html import format_html # Statusni rangli qilish uchun (ixtiyoriy)

class InstallmentPaymentInline(admin.TabularInline):
    model = InstallmentPayment
    extra = 0
    # Endi bu maydonlar mavjud
    readonly_fields = ('payment_date', 'amount', 'payment_method', 'received_by')
    can_delete = False
    ordering = ('-payment_date',)

    def has_add_permission(self, request, obj=None):
        return False

# Yangi Inline: To'lov Grafigini ko'rsatish uchun
class PaymentScheduleInline(admin.TabularInline):
    model = PaymentSchedule
    extra = 0
    readonly_fields = ('due_date', 'amount_due', 'amount_paid', 'is_paid', 'payment_date')
    can_delete = False # Odatda grafikni qo'lda o'chirish kerak emas
    ordering = ('due_date',)

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(InstallmentPlan)
class InstallmentPlanAdmin(admin.ModelAdmin):
    # Yangilangan maydon nomlari bilan list_display
    list_display = (
        'id', 'sale_id', 'customer', 'initial_amount', 'interest_rate', 'term_months',
        'total_amount_due', # Yangi nom
        'amount_paid', 'remaining_amount_display', # remaining_amount uchun metod
        'display_next_payment_date', # next_payment_date uchun metod
        'status_colored', # Status uchun metod
        'created_at'
    )
    list_filter = ('status', 'customer', 'sale__kassa', 'term_months', 'interest_rate') # next_payment_date olib tashlandi
    search_fields = ('id', 'sale__id', 'customer__full_name', 'customer__phone_number')
    # readonly_fields ni ham yangilash
    readonly_fields = (
        'sale', 'customer', 'initial_amount', 'interest_rate', 'term_months',
        'total_amount_due', 'monthly_payment', 'down_payment', 'amount_paid',
        'remaining_amount', # Endi bu property
        'status', 'created_at', 'return_adjustment',
        'display_next_payment_date' # Buni ham readonly qilamiz
    )
    # Grafik va To'lovlar Inlinelarini qo'shamiz
    inlines = [PaymentScheduleInline, InstallmentPaymentInline]
    list_select_related = ('customer', 'sale__kassa') # Bu qoladi

    # Admin panelda yangi plan yaratish/o'chirishni taqiqlash
    def has_add_permission(self, request):
        return False
    # def has_delete_permission(self, request, obj=None): return False

    # Maxsus metodlar (list_display va readonly_fields uchun)
    @admin.display(description='Qolgan Qarz', ordering='-total_amount_due') # Taxminiy tartiblash
    def remaining_amount_display(self, obj):
        rem = obj.remaining_amount
        return f"{rem:,.2f} UZS" if rem is not None else "-"

    @admin.display(description='Keyingi To\'lov Sanasi', ordering='schedule__due_date') # Taxminiy tartiblash
    def display_next_payment_date(self, obj):
        next_date = obj.get_next_payment_due_date
        return next_date if next_date else "-"

    @admin.display(description='Holati', ordering='status')
    def status_colored(self, obj):
        color = 'black'
        if obj.status == InstallmentPlan.PlanStatus.ACTIVE:
            color = 'blue'
        elif obj.status == InstallmentPlan.PlanStatus.PAID:
            color = 'green'
        elif obj.status == InstallmentPlan.PlanStatus.OVERDUE:
            color = 'red'
        elif obj.status == InstallmentPlan.PlanStatus.CANCELLED:
            color = 'grey'
        return format_html('<b style="color: {};">{}</b>', color, obj.get_status_display())

    # remaining_amount property sini list_display da ishlatish uchun
    # (lekin sorting to'g'ri ishlamasligi mumkin)
    def remaining_amount(self, obj):
        return obj.remaining_amount
    # remaining_amount.admin_order_field = '????' # Buni hisoblash qiyin

@admin.register(InstallmentPayment)
class InstallmentPaymentAdmin(admin.ModelAdmin):
    list_display = ('plan_link', 'amount', 'payment_date', 'payment_method', 'received_by')
    list_filter = ('payment_method', 'payment_date', 'received_by', 'plan__status') # plan__status qo'shildi
    search_fields = ('plan__id', 'plan__customer__full_name', 'received_by__username')
    readonly_fields = ('plan', 'amount', 'payment_date', 'payment_method', 'received_by')
    list_select_related = ('plan__customer', 'received_by')

    @admin.display(description='Nasiya Rejasi', ordering='plan__id')
    def plan_link(self, obj):
         from django.urls import reverse
         from django.utils.html import format_html
         link = reverse("admin:installments_installmentplan_change", args=[obj.plan.id])
         return format_html('<a href="{}">Reja #{} ({})</a>', link, obj.plan.id, obj.plan.customer)

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    # def has_delete_permission(self, request, obj=None): return False # O'chirish mumkinmi?

# PaymentSchedule ni ham admin panelda ko'rsatish (ixtiyoriy)
@admin.register(PaymentSchedule)
class PaymentScheduleAdmin(admin.ModelAdmin):
    list_display = ('plan_link', 'due_date', 'amount_due', 'amount_paid', 'is_paid', 'payment_date')
    list_filter = ('is_paid', 'due_date', 'plan__status')
    search_fields = ('plan__id', 'plan__customer__full_name')
    readonly_fields = ('plan', 'due_date', 'amount_due', 'amount_paid', 'is_paid', 'payment_date') # O'zgartirib bo'lmaydi
    list_select_related = ('plan__customer',)

    @admin.display(description='Nasiya Rejasi', ordering='plan__id')
    def plan_link(self, obj):
        # InstallmentPaymentAdmin dagi kabi link
         from django.urls import reverse
         from django.utils.html import format_html
         link = reverse("admin:installments_installmentplan_change", args=[obj.plan.id])
         return format_html('<a href="{}">Reja #{} ({})</a>', link, obj.plan.id, obj.plan.customer)

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False