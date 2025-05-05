# reports/services.py
from django.db.models import Sum, Count, F, DecimalField, Q, Value, Case, When, CharField
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, Cast
from django.utils import timezone
from datetime import timedelta, datetime, date, time
from decimal import Decimal

# --- Model importlari ---
from users.models import User, UserProfile
from sales.models import Sale, SaleItem, Customer, KassaTransaction, Kassa
from products.models import Product, Category
from inventory.models import ProductStock
from installments.models import InstallmentPlan

# --- Kassa Balansi ---
def get_kassa_balance(kassa_id):
    if not kassa_id: return None # ID berilmasa None qaytaramiz
    try:
        kassa = Kassa.objects.get(pk=kassa_id)
        income_types = [ KassaTransaction.TransactionType.SALE, KassaTransaction.TransactionType.INSTALLMENT_PAYMENT, KassaTransaction.TransactionType.CASH_IN ]
        expense_types = [ KassaTransaction.TransactionType.CASH_OUT, KassaTransaction.TransactionType.RETURN_REFUND ]
        balance_agg = KassaTransaction.objects.filter(kassa=kassa).aggregate(
            total_income=Sum( Case(When(transaction_type__in=income_types, then=F('amount')), default=Value(Decimal(0))), output_field=DecimalField(decimal_places=2) ),
            total_expense=Sum( Case(When(transaction_type__in=expense_types, then=F('amount')), default=Value(Decimal(0))), output_field=DecimalField(decimal_places=2) )
        )
        income = balance_agg.get('total_income') or Decimal(0)
        expense = balance_agg.get('total_expense') or Decimal(0)
        return income - expense
    except Kassa.DoesNotExist: return Decimal(0) # Kassa topilmasa balans 0
    except Exception as e: print(f"Error calculating kassa balance for {kassa_id}: {e}"); return None

# --- Dashboard ---
def get_dashboard_stats(kassa_id=None):
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    thirty_days_ago = today - timedelta(days=30)

    sales_today_qs = Sale.objects.filter(
        created_at__date=today,
        status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]
    )
    sales_this_month_qs = Sale.objects.filter(
        created_at__date__gte=start_of_month,
        status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]
    )
    sale_items_last_30_days = SaleItem.objects.filter(
        sale__created_at__date__gte=thirty_days_ago,
        sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]
    )

    today_sales_agg = sales_today_qs.aggregate(
        total_uzs=Sum('total_amount_uzs', default=Decimal(0)), count=Count('id')
    )
    monthly_sales_agg = sales_this_month_qs.aggregate(
        total_uzs=Sum('total_amount_uzs', default=Decimal(0)), count=Count('id')
    )

    weekly_sales_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        daily_total = sales_this_month_qs.filter(created_at__date=day).aggregate(
            total=Sum('total_amount_uzs', default=Decimal(0))
        )['total'] or Decimal(0)
        weekly_sales_data.append({'day': day.strftime('%Y-%m-%d'), 'daily_total': daily_total})

    top_products = sale_items_last_30_days.values('product__name') \
                    .annotate(total_quantity_sold=Sum('quantity')) \
                    .order_by('-total_quantity_sold')[:5]

    kassa_balance_val = get_kassa_balance(kassa_id)
    kassa_name_val = Kassa.objects.filter(pk=kassa_id).values_list('name', flat=True).first() if kassa_id else None

    return {
        'today_sales_uzs': today_sales_agg['total_uzs'],
        'today_sales_count': today_sales_agg.get('count', 0),
        'monthly_sales_uzs': monthly_sales_agg['total_uzs'],
        'monthly_sales_count': monthly_sales_agg.get('count', 0),
        'total_products': Product.objects.filter(is_active=True).count(),
        'low_stock_products': ProductStock.objects.filter(quantity__lte=F('minimum_stock_level')).count(),
        'total_customers': Customer.objects.count(),
        'new_customers_today': Customer.objects.filter(created_at__date=today).count(),
        'kassa_balance': kassa_balance_val,
        'kassa_name': kassa_name_val,
        'weekly_sales_chart': weekly_sales_data,
        'top_products_chart': list(top_products),
    }

# --- Sotuvlar Hisoboti ---
def get_sales_report_data(start_date, end_date, currency='UZS', seller_id=None, kassa_id=None, payment_type=None, group_by=None): # <= ASL NOM
    filters = Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])
    if start_date: filters &= Q(created_at__gte=datetime.combine(start_date, time.min)) # <= ASL NOM
    if end_date: filters &= Q(created_at__lte=datetime.combine(end_date, time.max)) # <= ASL NOM
    if seller_id: filters &= Q(seller_id=seller_id)
    if kassa_id: filters &= Q(kassa_id=kassa_id)
    if payment_type: filters &= Q(payment_type=payment_type)

    sales_qs = Sale.objects.filter(filters)
    amount_field = 'total_amount_uzs' if currency == 'UZS' else 'total_amount_usd'
    total_sum = sales_qs.aggregate(total=Sum(amount_field, default=Decimal(0)))['total']

    chart_data, details = [], []
    trunc_func, date_format = None, None
    if group_by == 'day': trunc_func, date_format = TruncDay, '%Y-%m-%d'
    elif group_by == 'week': trunc_func, date_format = TruncWeek, '%Y / W%W'
    elif group_by == 'month': trunc_func, date_format = TruncMonth, '%Y-%m'

    if trunc_func:
        chart_data_query = sales_qs.annotate(period=trunc_func('created_at')) \
                                .values('period') \
                                .annotate(period_total=Sum(amount_field, default=Decimal(0))) \
                                .order_by('period')
        chart_data = [{'period': item['period'].strftime(date_format),
                       'total': item.get('period_total') or Decimal(0)} for item in chart_data_query]
    else:
        details_query = sales_qs.select_related('seller', 'customer', 'kassa') \
                             .annotate(items_count=Count('items')) \
                             .values('id', 'created_at', 'seller__username', 'customer__full_name',
                                     'kassa__name', 'payment_type', amount_field, 'items_count') \
                             .order_by('-created_at')
        details = [{**item, 'created_at': item['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                   'total_amount': item.get(amount_field) or Decimal(0)} for item in details_query]

    return {'total': total_sum, 'details': details, 'chart_data': chart_data}

# --- Mahsulotlar Hisoboti ---
# FUNKSIYA TA'RIFINI O'ZGARTIRING:
def get_products_report_data(start_date, end_date, category_id=None, currency='UZS'): # <= ASL NOM
    filters = Q(sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])
    if start_date: filters &= Q(sale__created_at__gte=datetime.combine(start_date, time.min)) # <= ASL NOM
    if end_date: filters &= Q(sale__created_at__lte=datetime.combine(end_date, time.max)) # <= ASL NOM

    if category_id: filters &= Q(product__category_id=category_id)

    sale_items_qs = SaleItem.objects.filter(filters).select_related('product__category')
    price_field_f = F('price_at_sale_uzs' if currency == 'UZS' else 'price_at_sale_usd')

    product_summary = sale_items_qs.values('product_id', 'product__name', 'product__category__name') \
                        .annotate(total_quantity=Sum('quantity', default=0),
                                  total_amount=Sum(F('quantity') * price_field_f, output_field=DecimalField(decimal_places=2), default=Decimal(0))) \
                        .order_by('-total_amount')

    total_sales_amount = product_summary.aggregate(total=Sum('total_amount', default=Decimal(0)))['total']
    pie_chart_data = []
    if total_sales_amount and total_sales_amount > 0:
        pie_chart_data = [{'product_name': p['product__name'],
                           'percentage': float(round((p['total_amount'] / total_sales_amount) * 100, 2)) if p['total_amount'] else 0.0
                          } for p in product_summary if p.get('total_amount')]
    return {'table_data': list(product_summary), 'pie_chart_data': pie_chart_data}

# --- Sotuvchilar Hisoboti ---
def get_sellers_report_data(start_date, end_date, currency='UZS'): # <= ASL NOM
    filters = Q(seller__isnull=False, status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])
    if start_date: filters &= Q(created_at__gte=datetime.combine(start_date, time.min)) # <= ASL NOM
    if end_date: filters &= Q(created_at__lte=datetime.combine(end_date, time.max)) # <= ASL NOM

    sales_qs = Sale.objects.filter(filters).select_related('seller__profile')
    amount_field = 'total_amount_uzs' if currency == 'UZS' else 'total_amount_usd'

    seller_summary = sales_qs.values('seller_id', 'seller__username', 'seller__profile__full_name') \
                        .annotate(total_sales_amount=Sum(amount_field, default=Decimal(0)),
                                  total_sales_count=Count('id')) \
                        .order_by('-total_sales_amount')

    seller_ids = [s['seller_id'] for s in seller_summary]
    items_sold_agg = SaleItem.objects.filter(
        sale__seller_id__in=seller_ids,
        sale__created_at__gte=datetime.combine(start_date, time.min) if start_date else None,  # <= ASL NOM
        sale__created_at__lte=datetime.combine(end_date, time.max) if end_date else None,  # <= ASL NOM
        sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]
    ).values('sale__seller_id').annotate(total_items=Sum('quantity', default=0))
    items_sold_map = {item['sale__seller_id']: item['total_items'] for item in items_sold_agg}

    report_list = [{ 'seller_id': s['seller_id'], 'username': s['seller__username'],
                     'full_name': s['seller__profile__full_name'],
                     'total_sales_amount': s.get('total_sales_amount') or Decimal(0),
                     'total_sales_count': s.get('total_sales_count', 0),
                     'total_items_sold': items_sold_map.get(s['seller_id'], 0)
                   } for s in seller_summary]
    return {'table_data': report_list}

# --- Nasiyalar Hisoboti ---
def get_installments_report_data(start_date=None, end_date=None, customer_id=None, status=None): # <= ASL NOMLAR
    filters = Q()
    if start_date: filters &= Q(created_at__gte=datetime.combine(start_date, time.min)) # <= ASL NOM
    if end_date: filters &= Q(created_at__lte=datetime.combine(end_date, time.max)) # <= ASL NOM
    if customer_id: filters &= Q(customer_id=customer_id)
    if status: filters &= Q(status=status)

    plans_qs = InstallmentPlan.objects.filter(filters).select_related('customer', 'sale__kassa')
    remaining_expression = Cast(F('total_due') - F('return_adjustment') - F('amount_paid'), output_field=DecimalField(max_digits=17, decimal_places=2))
    status_display_expression = Case(*[When(status=val, then=Value(label)) for val, label in InstallmentPlan.PlanStatus.choices], default=Value('Noma\'lum'), output_field=CharField())

    report_values = plans_qs.annotate(remaining_amount=remaining_expression, status_display=status_display_expression) \
                        .values('id', 'sale_id', 'customer__full_name', 'customer__phone_number',
                                'total_due', 'amount_paid', 'return_adjustment', 'remaining_amount',
                                'next_payment_date', 'status', 'status_display', 'created_at') \
                        .order_by('-created_at')
    return list(report_values)