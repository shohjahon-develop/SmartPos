# installments/admin.py
from django.contrib import admin
from django.db.models import Sum
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from decimal import Decimal

from .models import InstallmentPlan, InstallmentPayment
from sales.models import KassaTransaction  # Agar KassaTransaction yaratmoqchi bo'lsak


# from django.conf import settings # Agar User kerak bo'lsa

class InstallmentPaymentInline(admin.TabularInline):
    model = InstallmentPayment
    extra = 1  # Yangi plan yaratganda bitta bo'sh to'lov formasi chiqadi
    fields = ('amount', 'payment_method', 'payment_date', 'received_by')
    # Admin panelidan inline orqali to'lov qo'shishda received_by va payment_date ni
    # save_formset da o'rnatamiz.

    # Agar received_by uchun faqat aktiv userlarni ko'rsatmoqchi bo'lsangiz:
    # def formfield_for_foreignkey(self, db_field, request, **kwargs):
    #     if db_field.name == "received_by":
    #         from django.contrib.auth import get_user_model
    #         User = get_user_model()
    #         kwargs["queryset"] = User.objects.filter(is_active=True)
    #     return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(InstallmentPlan)
class InstallmentPlanAdmin(admin.ModelAdmin):
    list_display = (
    'id', 'sale_id_link', 'customer_link', 'total_due', 'amount_paid', 'remaining_amount', 'next_payment_date',
    'status', 'created_at')
    list_filter = ('status', 'next_payment_date', 'customer__full_name')
    search_fields = ('id', 'sale__id', 'customer__full_name', 'customer__phone_number')
    readonly_fields = (
    'remaining_amount', 'created_at', 'return_adjustment')  # amount_paid ham readonly bo'lishi mumkin
    inlines = [InstallmentPaymentInline]
    list_select_related = ('customer', 'sale')
    autocomplete_fields = ['sale', 'customer']  # Tanlashni osonlashtirish

    # Yangi plan yaratishga ruxsat
    def has_add_permission(self, request):
        return True

    def sale_id_link(self, obj):
        if obj.sale:
            link = reverse("admin:sales_sale_change", args=[obj.sale.id])
            return format_html('<a href="{}">Sotuv #{}</a>', link, obj.sale.id)
        return "-"

    sale_id_link.short_description = 'Sotuv ID'
    sale_id_link.admin_order_field = 'sale__id'

    def customer_link(self, obj):
        if obj.customer:
            link = reverse("admin:sales_customer_change", args=[obj.customer.id])
            return format_html('<a href="{}">{}</a>', link, obj.customer.full_name)
        return "-"

    customer_link.short_description = 'Mijoz'
    customer_link.admin_order_field = 'customer__full_name'

    # Admin panelidan yangi plan yaratilganda ba'zi maydonlarni avtomatik to'ldirish
    def get_changeform_initial_data(self, request):
        # Agar 'sale_id' URL parametrida kelgan bo'lsa (masalan, Sotuv adminidan "Nasiya qo'shish" linki orqali)
        # Hozircha bu logika yo'q, lekin kelajakda qo'shish mumkin
        initial = super().get_changeform_initial_data(request)
        # initial['next_payment_date'] = timezone.now().date() + timezone.timedelta(days=30) # Masalan
        return initial

    def save_model(self, request, obj, form, change):
        """Admin panelidan Plan saqlanganda"""
        # Agar 'sale' tanlangan bo'lsa va 'total_due' yoki 'customer' bo'sh bo'lsa,
        # ularni sotuvdan olishga harakat qilamiz
        if obj.sale:
            if not obj.total_due or obj.total_due == Decimal(0):
                obj.total_due = obj.sale.total_amount_uzs  # Asosiy valyuta UZS deb faraz qilamiz
            if not obj.customer and obj.sale.customer:
                obj.customer = obj.sale.customer

        # Boshlang'ich amount_paid inline orqali keladi yoki keyin alohida to'lov qilinadi
        # Agar formda amount_paid maydoni bo'lsa, uni ishlatish mumkin
        # Hozircha uni inline ga qoldiramiz

        super().save_model(request, obj, form, change)  # Avval Plan ni saqlaymiz
        # update_status keyinroq, formset saqlangandan keyin chaqiriladi

    def save_formset(self, request, form, formset, change):
        """Inline to'lovlar (InstallmentPaymentInline) saqlanganda"""
        instances = formset.save(commit=False)  # Avval commit qilmaymiz
        plan = form.instance  # Joriy InstallmentPlan

        newly_added_payments_total = Decimal(0)

        for payment_obj in instances:
            if not payment_obj.pk:  # Agar bu yangi qo'shilgan to'lov bo'lsa
                payment_obj.plan = plan  # Plan ga bog'lash (agar formset avtomatik qilmasa)
                if not payment_obj.received_by:
                    payment_obj.received_by = request.user
                if not payment_obj.payment_date:
                    payment_obj.payment_date = timezone.now()
                newly_added_payments_total += payment_obj.amount
            payment_obj.save()  # Har bir to'lovni saqlash

        formset.save_m2m()  # ManyToMany (agar bo'lsa)

        # Agar yangi to'lovlar qo'shilgan bo'lsa, Plan ning amount_paid ni yangilash
        if newly_added_payments_total > 0:
            # Bu yerda atomik operatsiya qilish yaxshi bo'lardi, lekin admin uchun soddalashtiramiz
            plan.amount_paid = (plan.amount_paid or Decimal(0)) + newly_added_payments_total
            plan.save(update_fields=['amount_paid'])  # Faqat amount_paid ni yangilash

            # Yangi qo'shilgan naqd/karta to'lovlar uchun Kassa Tranzaksiyasi yaratish
            # (Test uchun, API dagi kabi to'liq logika shart emas)
            for payment_obj in instances:
                if payment_obj.pk and payment_obj.amount == newly_added_payments_total and payment_obj.payment_method in [
                    InstallmentPayment.PaymentMethod.CASH,
                    InstallmentPayment.PaymentMethod.CARD]:  # Faqat yangi qo'shilgan va summasi mos keladigan
                    # Bu shart to'g'ri emas, chunki instances da yangi qo'shilganlar pk ga ega bo'lmaydi saqlashdan oldin
                    # Yaxshiroq yo'l - faqat yangi qo'shilgan va saqlanganlarni tekshirish
                    # Hozircha, agar API orqali to'lov qilinsa, KassaTransaction u yerda yaratiladi.
                    # Admin panelidan qo'shilgan to'lovlar uchun KassaTransaction yaratishni
                    # InstallmentPayment.save() metodiga ko'chirish kerak bo'ladi.
                    # Bu yerda sodda qoldiramiz, test uchun asosiy maqsad Plan ni yangilash.
                    pass

        # Plan statusini eng oxirida yangilash
        if plan.pk:  # Plan saqlangan bo'lishi kerak
            plan.update_status(force_save=True)


@admin.register(InstallmentPayment)
class InstallmentPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'plan_link', 'amount', 'payment_date', 'payment_method', 'received_by_username')
    list_filter = ('payment_method', 'payment_date', 'received_by', 'plan__status')
    search_fields = ('id', 'plan__id', 'plan__customer__full_name', 'received_by__username')
    readonly_fields = ('payment_date',)  # Odatda avtomatik
    fields = ('plan', 'amount', 'payment_method', 'received_by', 'payment_date')  # Ko'rsatiladigan maydonlar
    autocomplete_fields = ['plan', 'received_by']
    list_select_related = ('plan__customer', 'plan__sale', 'received_by')  # Bog'liqliklarni oldindan olish

    # Yangi to'lov qo'shishga ruxsat
    def has_add_permission(self, request):
        return True

    def plan_link(self, obj):
        if obj.plan:
            link = reverse("admin:installments_installmentplan_change", args=[obj.plan.id])
            return format_html('<a href="{}">Nasiya #{}</a>', link, obj.plan.id)
        return "-"

    plan_link.short_description = 'Nasiya Rejasi'

    def received_by_username(self, obj):
        if obj.received_by:
            return obj.received_by.username
        return "-"

    received_by_username.short_description = 'Qabul qilgan xodim'

    def save_model(self, request, obj, form, change):
        """Admin panelidan To'lov saqlanganda"""
        is_new_payment = not obj.pk

        if is_new_payment:  # Agar yangi to'lov bo'lsa
            if not obj.received_by:
                obj.received_by = request.user
            if not obj.payment_date:
                obj.payment_date = timezone.now()

        # To'lov obyektini saqlash
        super().save_model(request, obj, form, change)

        # --- Plan va KassaTranzaksiyalarini yangilash ---
        plan = obj.plan
        if plan:
            # 1. Plan ning amount_paid maydonini QAYTA HISOBLASH
            # Bu planga tegishli BARCHA to'lovlar summasini olish
            all_payments_sum = plan.payments.all().aggregate(total=Sum('amount'))['total'] or Decimal(0)

            if plan.amount_paid != all_payments_sum:  # Faqat o'zgargan bo'lsa saqlaymiz
                plan.amount_paid = all_payments_sum
                plan.save(update_fields=['amount_paid'])  # Faqat amount_paid ni yangilaymiz

            # 2. Plan statusini yangilash
            plan.update_status(force_save=True)

            # 3. Kassa Tranzaksiyasini Yaratish (Yangi to'lovlar uchun)
            # Bu logika InstallmentPayment modelining save() metodida bo'lsa yaxshiroq.
            # Hozircha bu yerda qoldiramiz (test uchun).
            # Agar to'lov API orqali qilingan bo'lsa, u yerda KassaTransaction yaratilgan bo'ladi.
            # Admin panelidan qo'shilganda ham yaratamiz.
            if is_new_payment and obj.payment_method in [InstallmentPayment.PaymentMethod.CASH,
                                                         InstallmentPayment.PaymentMethod.CARD]:
                if hasattr(plan, 'sale') and plan.sale and hasattr(plan.sale,
                                                                   'kassa'):  # Sotuv va kassa mavjudligini tekshirish
                    KassaTransaction.objects.create(
                        # store maydoni yo'q
                        kassa=plan.sale.kassa,
                        amount=obj.amount,
                        transaction_type=KassaTransaction.TransactionType.INSTALLMENT_PAYMENT,
                        user=request.user,  # Yoki obj.received_by
                        comment=f"Admin panelidan Nasiya #{plan.id} uchun to'lov (ID: {obj.id})",
                        related_installment_payment=obj
                    )
                else:
                    print(
                        f"WARNING: Could not create KassaTransaction for payment {obj.id}. Sale or Kassa not found on plan.")


# # installments/admin.py
# from django.contrib import admin
# from .models import InstallmentPlan, InstallmentPayment, PaymentSchedule # PaymentSchedule ni import qiling
# from django.utils.html import format_html # Statusni rangli qilish uchun (ixtiyoriy)
#
# class InstallmentPaymentInline(admin.TabularInline):
#     model = InstallmentPayment
#     extra = 0
#     # Endi bu maydonlar mavjud
#     readonly_fields = ('payment_date', 'amount', 'payment_method', 'received_by')
#     can_delete = False
#     ordering = ('-payment_date',)
#
#     def has_add_permission(self, request, obj=None):
#         return False
#
# # Yangi Inline: To'lov Grafigini ko'rsatish uchun
# class PaymentScheduleInline(admin.TabularInline):
#     model = PaymentSchedule
#     extra = 0
#     readonly_fields = ('due_date', 'amount_due', 'amount_paid', 'is_paid', 'payment_date')
#     can_delete = False # Odatda grafikni qo'lda o'chirish kerak emas
#     ordering = ('due_date',)
#
#     def has_add_permission(self, request, obj=None):
#         return False
#
# @admin.register(InstallmentPlan)
# class InstallmentPlanAdmin(admin.ModelAdmin):
#     # Yangilangan maydon nomlari bilan list_display
#     list_display = (
#         'id', 'sale_id', 'customer', 'initial_amount', 'interest_rate', 'term_months',
#         'total_amount_due', # Yangi nom
#         'amount_paid', 'remaining_amount_display', # remaining_amount uchun metod
#         'display_next_payment_date', # next_payment_date uchun metod
#         'status_colored', # Status uchun metod
#         'created_at'
#     )
#     list_filter = ('status', 'customer', 'sale__kassa', 'term_months', 'interest_rate') # next_payment_date olib tashlandi
#     search_fields = ('id', 'sale__id', 'customer__full_name', 'customer__phone_number')
#     # readonly_fields ni ham yangilash
#     readonly_fields = (
#         'sale', 'customer', 'initial_amount', 'interest_rate', 'term_months',
#         'total_amount_due', 'monthly_payment', 'down_payment', 'amount_paid',
#         'remaining_amount', # Endi bu property
#         'status', 'created_at', 'return_adjustment',
#         'display_next_payment_date' # Buni ham readonly qilamiz
#     )
#     # Grafik va To'lovlar Inlinelarini qo'shamiz
#     inlines = [PaymentScheduleInline, InstallmentPaymentInline]
#     list_select_related = ('customer', 'sale__kassa') # Bu qoladi
#
#     # Admin panelda yangi plan yaratish/o'chirishni taqiqlash
#     def has_add_permission(self, request):
#         return False
#     # def has_delete_permission(self, request, obj=None): return False
#
#     # Maxsus metodlar (list_display va readonly_fields uchun)
#     @admin.display(description='Qolgan Qarz', ordering='-total_amount_due') # Taxminiy tartiblash
#     def remaining_amount_display(self, obj):
#         rem = obj.remaining_amount
#         return f"{rem:,.2f} UZS" if rem is not None else "-"
#
#     @admin.display(description='Keyingi To\'lov Sanasi', ordering='schedule__due_date') # Taxminiy tartiblash
#     def display_next_payment_date(self, obj):
#         next_date = obj.get_next_payment_due_date
#         return next_date if next_date else "-"
#
#     @admin.display(description='Holati', ordering='status')
#     def status_colored(self, obj):
#         color = 'black'
#         if obj.status == InstallmentPlan.PlanStatus.ACTIVE:
#             color = 'blue'
#         elif obj.status == InstallmentPlan.PlanStatus.PAID:
#             color = 'green'
#         elif obj.status == InstallmentPlan.PlanStatus.OVERDUE:
#             color = 'red'
#         elif obj.status == InstallmentPlan.PlanStatus.CANCELLED:
#             color = 'grey'
#         return format_html('<b style="color: {};">{}</b>', color, obj.get_status_display())
#
#     # remaining_amount property sini list_display da ishlatish uchun
#     # (lekin sorting to'g'ri ishlamasligi mumkin)
#     def remaining_amount(self, obj):
#         return obj.remaining_amount
#     # remaining_amount.admin_order_field = '????' # Buni hisoblash qiyin
#
# @admin.register(InstallmentPayment)
# class InstallmentPaymentAdmin(admin.ModelAdmin):
#     list_display = ('plan_link', 'amount', 'payment_date', 'payment_method', 'received_by')
#     list_filter = ('payment_method', 'payment_date', 'received_by', 'plan__status') # plan__status qo'shildi
#     search_fields = ('plan__id', 'plan__customer__full_name', 'received_by__username')
#     readonly_fields = ('plan', 'amount', 'payment_date', 'payment_method', 'received_by')
#     list_select_related = ('plan__customer', 'received_by')
#
#     @admin.display(description='Nasiya Rejasi', ordering='plan__id')
#     def plan_link(self, obj):
#          from django.urls import reverse
#          from django.utils.html import format_html
#          link = reverse("admin:installments_installmentplan_change", args=[obj.plan.id])
#          return format_html('<a href="{}">Reja #{} ({})</a>', link, obj.plan.id, obj.plan.customer)
#
#     def has_add_permission(self, request): return False
#     def has_change_permission(self, request, obj=None): return False
#     # def has_delete_permission(self, request, obj=None): return False # O'chirish mumkinmi?
#
# # PaymentSchedule ni ham admin panelda ko'rsatish (ixtiyoriy)
# @admin.register(PaymentSchedule)
# class PaymentScheduleAdmin(admin.ModelAdmin):
#     list_display = ('plan_link', 'due_date', 'amount_due', 'amount_paid', 'is_paid', 'payment_date')
#     list_filter = ('is_paid', 'due_date', 'plan__status')
#     search_fields = ('plan__id', 'plan__customer__full_name')
#     readonly_fields = ('plan', 'due_date', 'amount_due', 'amount_paid', 'is_paid', 'payment_date') # O'zgartirib bo'lmaydi
#     list_select_related = ('plan__customer',)
#
#     @admin.display(description='Nasiya Rejasi', ordering='plan__id')
#     def plan_link(self, obj):
#         # InstallmentPaymentAdmin dagi kabi link
#          from django.urls import reverse
#          from django.utils.html import format_html
#          link = reverse("admin:installments_installmentplan_change", args=[obj.plan.id])
#          return format_html('<a href="{}">Reja #{} ({})</a>', link, obj.plan.id, obj.plan.customer)
#
#     def has_add_permission(self, request): return False
#     def has_change_permission(self, request, obj=None): return False