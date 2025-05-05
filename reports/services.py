# reports/services.py
from django.db.models import Sum, Count, F, DecimalField, Q, Value, Case, When, OuterRef, Subquery
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, Cast
from django.utils import timezone
from datetime import timedelta, datetime, date
from decimal import Decimal

# --- Model importlari ---
from users.models import User, UserProfile # Store kerak emas
from sales.models import Sale, SaleItem, Customer, KassaTransaction, Kassa, SaleReturn
from products.models import Product, Category
from inventory.models import ProductStock, InventoryOperation
from installments.models import InstallmentPlan, InstallmentPayment

# --- Kassa Balansini Hisoblash Funksiyasi (O'zgarishsiz) ---
def get_kassa_balance(kassa_id):
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
    except Kassa.DoesNotExist: return Decimal(0)
    except Exception as e: print(f"Error calculating kassa balance for {kassa_id}: {e}"); return None

# --- Dashboard uchun statistika (Bitta do'kon uchun) ---
def get_dashboard_stats(kassa_id=None):
    today = timezone.now().date()
    start_of_month = today.replace(day=1)

    base_sales_filter = Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])

    today_sales_agg = Sale.objects.filter(base_sales_filter & Q(created_at__date=today)) \
                       .aggregate(total_uzs=Sum('total_amount_uzs', default=Decimal(0)),
                                  count=Count('id')) # default olib tashlandi

    monthly_sales_agg = Sale.objects.filter(base_sales_filter & Q(created_at__date__gte=start_of_month)) \
                         .aggregate(total_uzs=Sum('total_amount_uzs', default=Decimal(0)),
                                    count=Count('id')) # default olib tashlandi

    product_count = Product.objects.filter(is_active=True).count()
    low_stock_count = ProductStock.objects.filter(quantity__lte=F('minimum_stock_level')).count()
    customer_count = Customer.objects.count()
    new_customers_today = Customer.objects.filter(created_at__date=today).count()

    weekly_sales_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        daily_sales = Sale.objects.filter(base_sales_filter & Q(created_at__date=day)) \
                           .aggregate(daily_total=Sum('total_amount_uzs', default=Decimal(0)))
        weekly_sales_data.append({'day': day.strftime('%Y-%m-%d'),
                                  'daily_total': daily_sales.get('daily_total') or Decimal(0)})

    thirty_days_ago = today - timedelta(days=30)
    top_products = SaleItem.objects.filter(
            sale__created_at__date__gte=thirty_days_ago,
            sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]
        ).values('product__name') \
        .annotate(total_quantity_sold=Sum('quantity')) \
        .order_by('-total_quantity_sold')[:5]

    current_kassa_balance = None
    kassa_name = None
    if kassa_id:
         current_kassa_balance = get_kassa_balance(kassa_id)
         try:
             kassa = Kassa.objects.values('name').get(pk=kassa_id)
             kassa_name = kassa['name']
         except Kassa.DoesNotExist: kassa_name = "Noma'lum Kassa"

    return {
        'today_sales_uzs': today_sales_agg.get('total_uzs'),
        'today_sales_count': today_sales_agg.get('count', 0), # Count uchun 0 default
        'monthly_sales_uzs': monthly_sales_agg.get('total_uzs'),
        'monthly_sales_count': monthly_sales_agg.get('count', 0), # Count uchun 0 default
        'total_products': product_count,
        'low_stock_products': low_stock_count,
        'total_customers': customer_count,
        'new_customers_today': new_customers_today,
        'kassa_balance': current_kassa_balance,
        'kassa_name': kassa_name,
        'weekly_sales_chart': weekly_sales_data,
        'top_products_chart': list(top_products),
    }

# --- Sotuvlar Hisoboti (Bitta do'kon uchun) ---
def get_sales_report_data(start_date, end_date, currency='UZS', seller_id=None, kassa_id=None, payment_type=None, group_by=None):
    # store_id filtri kerak emas
    filters = Q(created_at__date__gte=start_date) & \
              Q(created_at__date__lte=end_date) & \
              Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])

    if seller_id: filters &= Q(seller_id=seller_id)
    if kassa_id: filters &= Q(kassa_id=kassa_id)
    if payment_type:
        if payment_type not in Sale.PaymentType.values: raise ValueError(f"Invalid payment type: {payment_type}")
        filters &= Q(payment_type=payment_type)

    sales_qs = Sale.objects.filter(filters)
    amount_field = 'total_amount_uzs' if currency == 'UZS' else 'total_amount_usd'
    total_sum = sales_qs.aggregate(total=Sum(amount_field, default=Decimal(0)))['total']

    chart_data = []
    details = []

    if group_by == 'day': trunc_func, date_format = TruncDay, '%Y-%m-%d'
    elif group_by == 'week': trunc_func, date_format = TruncWeek, '%Y / W%W'
    elif group_by == 'month': trunc_func, date_format = TruncMonth, '%Y-%m'
    else: trunc_func = None

    if trunc_func:
        chart_data_query = sales_qs.annotate(period=trunc_func('created_at')) \
                                .values('period') \
                                .annotate(period_total=Sum(amount_field, default=Decimal(0))) \
                                .order_by('period')
        chart_data = [{'period': item['period'].strftime(date_format),
                       'total': item.get('period_total') or Decimal(0)}
                      for item in chart_data_query]
        details = []
    else:
        details_query = sales_qs.select_related('seller', 'customer', 'kassa') \
                             .annotate(items_count=Count('items')) \
                             .values(
                                 'id', 'created_at', 'seller__username',
                                 'customer__full_name', 'kassa__name', 'payment_type',
                                 amount_field, # Direct field name
                                 'items_count'
                             ).order_by('-created_at')
        details = [
            {**item,
             'created_at': item['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
             'total_amount': item.get(amount_field) or Decimal(0)}
            for item in details_query
        ]
        chart_data = []

    return {'total': total_sum, 'details': details, 'chart_data': chart_data}

# --- Mahsulotlar Hisoboti (Bitta do'kon uchun) ---
def get_products_report_data(start_date, end_date, category_id=None, currency='UZS'):
    # store_id filtri kerak emas
    filters = Q(sale__created_at__date__gte=start_date) & \
              Q(sale__created_at__date__lte=end_date) & \
              Q(sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])

    if category_id: filters &= Q(product__category_id=category_id)

    sale_items_qs = SaleItem.objects.filter(filters).select_related('product', 'product__category')
    price_field_str = 'price_at_sale_uzs' if currency == 'UZS' else 'price_at_sale_usd'
    price_field_f = F(price_field_str)

    product_summary = sale_items_qs.values(
            'product_id', 'product__name', 'product__category__name'
        ).annotate(
            total_quantity=Sum('quantity', default=0),
            total_amount=Sum(F('quantity') * price_field_f, output_field=DecimalField(decimal_places=2), default=Decimal(0))
        ).order_by('-total_amount')

    total_sales_amount = product_summary.aggregate(total=Sum('total_amount', default=Decimal(0)))['total']

    pie_chart_data = []
    if total_sales_amount and total_sales_amount > 0:
        pie_chart_data = [
            {
                'product_name': p['product__name'],
                'percentage': float(round((p['total_amount'] / total_sales_amount) * 100, 2)) if p['total_amount'] else 0.0
            } for p in product_summary if p.get('total_amount')
        ]

    return { 'table_data': list(product_summary), 'pie_chart_data': pie_chart_data }

# --- Sotuvchilar Hisoboti (Bitta do'kon uchun) ---
def get_sellers_report_data(start_date, end_date, currency='UZS'):
    # store_id filtri kerak emas
    filters = Q(created_at__date__gte=start_date) & \
              Q(created_at__date__lte=end_date) & \
              Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & \
              Q(seller__isnull=False)

    sales_qs = Sale.objects.filter(filters).select_related('seller', 'seller__profile')
    amount_field = 'total_amount_uzs' if currency == 'UZS' else 'total_amount_usd'

    seller_summary = sales_qs.values(
            'seller_id', 'seller__username', 'seller__profile__full_name'
        ).annotate(
            total_sales_amount=Sum(amount_field, default=Decimal(0)),
            total_sales_count=Count('id'), # default olib tashlandi
        ).order_by('-total_sales_amount')

    # total_items_sold ni alohida hisoblash
    seller_ids = [s['seller_id'] for s in seller_summary]
    items_sold_agg = SaleItem.objects.filter(
        # sale__store_id=store_id, # <<<--- Olib tashlandi
        sale__seller_id__in=seller_ids,
        sale__created_at__date__gte=start_date,
        sale__created_at__date__lte=end_date,
        sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]
    ).values('sale__seller_id').annotate(
        total_items=Sum('quantity', default=0)
    )
    items_sold_map = {item['sale__seller_id']: item['total_items'] for item in items_sold_agg}

    report_list = []
    for summary in seller_summary:
        seller_id = summary['seller_id']
        report_list.append({
            'seller_id': seller_id,
            'username': summary['seller__username'],
            'full_name': summary['seller__profile__full_name'],
            'total_sales_amount': summary.get('total_sales_amount') or Decimal(0),
            'total_sales_count': summary.get('total_sales_count', 0), # default 0
            'total_items_sold': items_sold_map.get(seller_id, 0)
        })

    return { 'table_data': report_list }

# --- Nasiyalar Hisoboti (Bitta do'kon uchun) ---
def get_installments_report_data(start_date=None, end_date=None, customer_id=None, status=None):
    # store_id filtri kerak emas
    filters = Q()

    if start_date: filters &= Q(created_at__date__gte=start_date)
    if end_date: filters &= Q(created_at__date__lte=end_date)
    if customer_id: filters &= Q(customer_id=customer_id)
    if status:
        if status not in InstallmentPlan.PlanStatus.values: raise ValueError(f"Invalid installment status: {status}")
        filters &= Q(status=status)

    plans_qs = InstallmentPlan.objects.filter(filters).select_related('customer', 'sale')
    remaining_expression = Cast( F('total_due') - F('return_adjustment') - F('amount_paid'), output_field=DecimalField(decimal_places=2) )

    report_values = plans_qs.annotate(remaining=remaining_expression) \
                  .values(
                      'id', 'sale_id', 'customer__full_name', 'customer__phone_number',
                      'total_due', 'amount_paid', 'return_adjustment', 'remaining',
                      'next_payment_date', 'status', 'created_at'
                  ).order_by('-created_at')

    report_list = []
    for plan in report_values:
         report_list.append({
             'id': plan['id'],
             'sale_id': plan.get('sale_id'),
             'customer_full_name': plan.get('customer__full_name'),
             'customer_phone_number': plan.get('customer__phone_number'),
             'total_due': plan.get('total_due') or Decimal(0),
             'amount_paid': plan.get('amount_paid') or Decimal(0),
             'return_adjustment': plan.get('return_adjustment') or Decimal(0),
             'remaining_amount': plan.get('remaining') or Decimal(0),
             'next_payment_date': plan['next_payment_date'].strftime('%Y-%m-%d') if plan.get('next_payment_date') else None,
             'status': plan.get('status'),
             'status_display': InstallmentPlan.PlanStatus(plan.get('status')).label if plan.get('status') else None,
             'created_at': plan['created_at'].strftime('%Y-%m-%d %H:%M:%S') if plan.get('created_at') else None,
         })

    return report_list