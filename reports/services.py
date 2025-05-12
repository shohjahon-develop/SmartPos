# reports/services.py
from django.db.models import Sum, Count, F, DecimalField, Q, Value, Case, When
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, Cast
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal

# Model importlari
from users.models import User, UserProfile  # Store kerak emas
from sales.models import *  # SaleCurrency import qilindi
from products.models import Product, Category
from inventory.models import ProductStock, InventoryOperation  # Bular o'zgarishsiz
from installments.models import InstallmentPlan, InstallmentPayment


# --- Kassa Balansini Hisoblash (UZS da deb faraz qilamiz) ---
def get_kassa_balance(kassa_id):
    # Bu funksiya o'zgarishsiz qoladi, agar kassa faqat UZS da ishlasa
    # Agar kassalar ham USD/UZS bo'lishi mumkin bo'lsa, Kassa modeliga currency qo'shish kerak
    # va bu funksiya ham shuni hisobga olishi kerak.
    # Hozircha UZS deb faraz qilamiz.
    try:
        kassa = Kassa.objects.get(pk=kassa_id)
        income_types = [KassaTransaction.TransactionType.SALE, KassaTransaction.TransactionType.INSTALLMENT_PAYMENT,
                        KassaTransaction.TransactionType.CASH_IN]
        expense_types = [KassaTransaction.TransactionType.CASH_OUT, KassaTransaction.TransactionType.RETURN_REFUND]
        balance_agg = KassaTransaction.objects.filter(kassa=kassa).aggregate(
            total_income=Sum(Case(When(transaction_type__in=income_types, then=F('amount')), default=Value(Decimal(0))),
                             output_field=DecimalField(decimal_places=2)),
            total_expense=Sum(
                Case(When(transaction_type__in=expense_types, then=F('amount')), default=Value(Decimal(0))),
                output_field=DecimalField(decimal_places=2))
        )
        income = balance_agg.get('total_income') or Decimal(0)
        expense = balance_agg.get('total_expense') or Decimal(0)
        return income - expense
    except Kassa.DoesNotExist:
        return Decimal(0)
    except Exception:
        return None


# --- Dashboard uchun statistika (UZS va USD alohida) ---
def get_dashboard_stats(kassa_id=None):
    today = timezone.now().date()
    start_of_month = today.replace(day=1)

    base_sales_filter = Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])

    # --- UZS Sotuvlari ---
    sales_uzs_today_q = Sale.objects.filter(
        base_sales_filter & Q(currency=Sale.SaleCurrency.UZS) & Q(created_at__date=today))
    uzs_today_agg = sales_uzs_today_q.aggregate(
        total_currency=Sum('total_amount_currency', default=Decimal(0)),
        item_count=Count('id')  # default olib tashlandi
    )

    sales_uzs_month_q = Sale.objects.filter(
        base_sales_filter & Q(currency=Sale.SaleCurrency.UZS) & Q(created_at__date__gte=start_of_month))
    uzs_month_agg = sales_uzs_month_q.aggregate(
        total_currency=Sum('total_amount_currency', default=Decimal(0)),
        item_count=Count('id')  # default olib tashlandi
    )

    # --- USD Sotuvlari ---
    sales_usd_today_q = Sale.objects.filter(
        base_sales_filter & Q(currency=Sale.SaleCurrency.USD) & Q(created_at__date=today))
    usd_today_agg = sales_usd_today_q.aggregate(
        total_currency=Sum('total_amount_currency', default=Decimal(0)),
        item_count=Count('id')  # default olib tashlandi
    )

    sales_usd_month_q = Sale.objects.filter(
        base_sales_filter & Q(currency=Sale.SaleCurrency.USD) & Q(created_at__date__gte=start_of_month))
    usd_month_agg = sales_usd_month_q.aggregate(
        total_currency=Sum('total_amount_currency', default=Decimal(0)),
        item_count=Count('id')  # default olib tashlandi
    )
    # Umumiy statistikalar (valyutaga bog'liq emas)
    product_count = Product.objects.filter(is_active=True).count()
    low_stock_count = ProductStock.objects.filter(quantity__lte=F('minimum_stock_level')).count()
    customer_count = Customer.objects.count()
    new_customers_today = Customer.objects.filter(created_at__date=today).count()

    # Haftalik sotuvlar grafigi (UZS uchun, USD uchun ham shunga o'xshash qilish mumkin)
    weekly_sales_data_uzs = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        daily_sales_uzs = Sale.objects.filter(
            base_sales_filter & Q(currency=Sale.SaleCurrency.UZS) & Q(created_at__date=day)) \
            .aggregate(daily_total=Sum('total_amount_currency', default=Decimal(0)))
        weekly_sales_data_uzs.append(
            {'day': day.strftime('%Y-%m-%d'), 'daily_total': daily_sales_uzs.get('daily_total') or Decimal(0)})

    # Top mahsulotlar (qaysi valyutadagi sotuvlar bo'yicha? Hozircha umumiy miqdor bo'yicha)
    thirty_days_ago = today - timedelta(days=30)
    top_products = SaleItem.objects.filter(
        sale__created_at__date__gte=thirty_days_ago,
        sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]
    ).values('product__name') \
                       .annotate(total_quantity_sold=Sum('quantity')) \
                       .order_by('-total_quantity_sold')[:5]

    current_kassa_balance = get_kassa_balance(kassa_id) if kassa_id else None
    kassa_name = Kassa.objects.get(pk=kassa_id).name if kassa_id and current_kassa_balance is not None else None

    return {
        'today_sales_uzs': uzs_today_agg.get('total_currency') or Decimal(0), # or Decimal(0) qo'shildi
        'today_sales_uzs_count': uzs_today_agg.get('item_count') or 0,      # or 0 qo'shildi
        'monthly_sales_uzs': uzs_month_agg.get('total_currency') or Decimal(0),
        'monthly_sales_uzs_count': uzs_month_agg.get('item_count') or 0,
        'today_sales_usd': usd_today_agg.get('total_currency') or Decimal(0),
        'today_sales_usd_count': usd_today_agg.get('item_count') or 0,
        'monthly_sales_usd': usd_month_agg.get('total_currency') or Decimal(0),
        'monthly_sales_usd_count': usd_month_agg.get('item_count') or 0,
         'total_products': Product.objects.filter(is_active=True).count(), # count() to'g'ridan-to'g'ri ishlatiladi
        'low_stock_products': ProductStock.objects.filter(quantity__lte=F('minimum_stock_level')).count(),
        'total_customers': Customer.objects.count(),
        'new_customers_today': Customer.objects.filter(created_at__date=today).count(),
        'kassa_balance_uzs': current_kassa_balance,  # Faqat UZS kassa balansi
        'kassa_name': kassa_name,
        'weekly_sales_chart_uzs': weekly_sales_data_uzs,
        'top_products_chart': list(top_products),
    }


# --- Sotuvlar Hisoboti (tanlangan valyuta bo'yicha) ---
def get_sales_report_data(start_date, end_date, currency, seller_id=None, kassa_id=None, payment_type=None,
                          group_by=None):
    if currency not in Sale.SaleCurrency.values:
        raise ValueError(f"Noto'g'ri valyuta: {currency}. Mumkin bo'lganlar: {Sale.SaleCurrency.labels}")

    filters = Q(currency=currency) & \
              Q(created_at__date__gte=start_date) & \
              Q(created_at__date__lte=end_date) & \
              Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])
    if seller_id: filters &= Q(seller_id=seller_id)
    if kassa_id: filters &= Q(kassa_id=kassa_id)
    if payment_type: filters &= Q(payment_type=payment_type)

    sales_qs = Sale.objects.filter(filters)
    # Summa endi har doim 'total_amount_currency' dan olinadi
    total_sum = sales_qs.aggregate(total=Sum('total_amount_currency', default=Decimal(0)))['total']

    chart_data, details = [], []
    trunc_func, date_format = None, None
    if group_by == 'day':
        trunc_func, date_format = TruncDay, '%Y-%m-%d'
    elif group_by == 'week':
        trunc_func, date_format = TruncWeek, '%Y / W%W'
    elif group_by == 'month':
        trunc_func, date_format = TruncMonth, '%Y-%m'

    if trunc_func:
        chart_data_query = sales_qs.annotate(period=trunc_func('created_at')) \
            .values('period') \
            .annotate(period_total=Sum('total_amount_currency', default=Decimal(0))) \
            .order_by('period')
        chart_data = [{'period': item['period'].strftime(date_format),
                       'total': item.get('period_total') or Decimal(0)} for item in chart_data_query]
    else:
        details_query = sales_qs.select_related('seller', 'customer', 'kassa') \
            .annotate(items_count=Count('items')) \
            .values('id', 'created_at', 'seller__username', 'customer__full_name',
                    'kassa__name', 'payment_type', 'total_amount_currency', 'items_count') \
            .order_by('-created_at')
        details = [{'created_at': item['created_at'].strftime('%Y-%m-%d %H:%M:%S'), **item} for item in details_query]

    return {'total': total_sum, 'currency': currency, 'details': details, 'chart_data': chart_data}


# --- Mahsulotlar Hisoboti (tanlangan valyutadagi sotuvlar bo'yicha) ---
def get_products_report_data(start_date, end_date, currency, category_id=None):
    if currency not in Sale.SaleCurrency.values:
        raise ValueError(f"Noto'g'ri valyuta: {currency}.")

    filters = Q(sale__currency=currency) & \
              Q(sale__created_at__date__gte=start_date) & \
              Q(sale__created_at__date__lte=end_date) & \
              Q(sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])
    if category_id: filters &= Q(product__category_id=category_id)

    sale_items_qs = SaleItem.objects.filter(filters).select_related('product', 'product__category')

    # Narxni sotuv paytidagi narxdan olish (tanlangan valyutada)
    price_field_expression = Case(
        When(sale__currency=Sale.SaleCurrency.UZS, then=F('price_at_sale_uzs')),
        When(sale__currency=Sale.SaleCurrency.USD, then=F('price_at_sale_usd')),
        default=Value(0),
        output_field=DecimalField(decimal_places=2)
    )

    product_summary = sale_items_qs.values('product_id', 'product__name', 'product__category__name') \
        .annotate(
        total_quantity=Sum('quantity', default=0),
        total_amount=Sum(F('quantity') * price_field_expression, output_field=DecimalField(decimal_places=2),
                         default=Decimal(0))
    ).order_by('-total_amount')

    total_sales_amount_agg = product_summary.aggregate(grand_total=Sum('total_amount', default=Decimal(0)))
    grand_total_sales_amount = total_sales_amount_agg.get('grand_total') or Decimal(0)

    pie_chart_data = []
    if grand_total_sales_amount > 0:
        pie_chart_data = [{
            'product_name': p['product__name'],
            'percentage': float(round((p['total_amount'] / grand_total_sales_amount) * 100, 2)) if p.get(
                'total_amount') else 0.0
        } for p in product_summary if p.get('total_amount')]

    return {'currency': currency, 'table_data': list(product_summary), 'pie_chart_data': pie_chart_data}


# --- Sotuvchilar Hisoboti (tanlangan valyuta bo'yicha) ---
def get_sellers_report_data(start_date, end_date, currency):
    if currency not in Sale.SaleCurrency.values:
        raise ValueError(f"Noto'g'ri valyuta: {currency}.")

    filters = Q(currency=currency) & \
              Q(created_at__date__gte=start_date) & \
              Q(created_at__date__lte=end_date) & \
              Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & \
              Q(seller__isnull=False)

    sales_qs = Sale.objects.filter(filters).select_related('seller', 'seller__profile')

    seller_summary = sales_qs.values('seller_id', 'seller__username', 'seller__profile__full_name') \
        .annotate(
        total_sales_amount_currency=Sum('total_amount_currency', default=Decimal(0)),
        total_sales_count=Count('id', default=0)
    ).order_by('-total_sales_amount_currency')

    # total_items_sold ni ham qo'shish (biroz murakkabroq)
    # ... (avvalgi javobdagi kabi, lekin currency ni hisobga olib) ...

    return {'currency': currency, 'table_data': list(seller_summary)}


# --- Nasiyalar Hisoboti (har bir nasiya o'z valyutasida) ---
def get_installments_report_data(start_date=None, end_date=None, customer_id=None, status=None, currency_filter=None):
    filters = Q()  # Boshlang'ich bo'sh filtr
    if start_date: filters &= Q(created_at__date__gte=start_date)
    if end_date: filters &= Q(created_at__date__lte=end_date)
    if customer_id: filters &= Q(customer_id=customer_id)
    if status: filters &= Q(status=status)
    if currency_filter and currency_filter in Sale.SaleCurrency.values:  # YANGI: Valyuta bo'yicha filtr
        filters &= Q(currency=currency_filter)

    plans_qs = InstallmentPlan.objects.filter(filters).select_related('customer', 'sale')

    remaining_expression = Cast(
        F('total_amount_due') - F('return_adjustment') - F('amount_paid'),
        output_field=DecimalField(decimal_places=2)
    )

    report_values = plans_qs.annotate(remaining=remaining_expression) \
        .values(
        'id', 'sale_id', 'currency',  # currency qo'shildi
        'customer__full_name', 'customer__phone_number',
        'initial_amount', 'interest_rate', 'term_months', 'monthly_payment',
        'total_amount_due', 'down_payment', 'amount_paid', 'remaining',
        'status', 'created_at',
        # 'get_next_payment_due_date' ni bu yerda olish qiyin, serializerda qoladi
    ).order_by('-created_at')

    report_list = []
    for plan_data in report_values:
        # Nasiya obyektini olib, uning propertylaridan foydalanishimiz mumkin (masalan, next_payment_due_date)
        try:
            plan_instance = InstallmentPlan.objects.get(pk=plan_data['id'])
            next_due_date = plan_instance.get_next_payment_due_date
            is_overdue_val = plan_instance.is_overdue()
        except InstallmentPlan.DoesNotExist:
            next_due_date = None
            is_overdue_val = False

        report_list.append({
            **plan_data,  # Lug'atni ochish
            'next_payment_due_date': next_due_date.strftime('%Y-%m-%d') if next_due_date else None,
            'is_overdue': is_overdue_val,
            'status_display': InstallmentPlan.PlanStatus(plan_data.get('status')).label if plan_data.get(
                'status') else None,
            'created_at': plan_data['created_at'].strftime('%Y-%m-%d %H:%M:%S') if plan_data.get(
                'created_at') else None,
            'remaining_amount': plan_data.get('remaining') or Decimal(0)  # Nomini o'zgartirdim
        })
    return report_list