# reports/services.py
from django.db.models import Sum, Count, F, DecimalField, Q, Value, Case, When
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, Cast
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal

# Model importlari
from users.models import User, UserProfile
from sales.models import *
from products.models import Product, Category
from inventory.models import ProductStock, InventoryOperation
from installments.models import InstallmentPlan, InstallmentPayment


# --- YORDAMCHI FUNKSIYA: DAVR BO'YICHA SANA ORALIG'INI OLISH ---
def get_date_range_from_period(period_type, start_date_str=None, end_date_str=None):
    today = timezone.now().date()
    start_date, end_date = None, None
    period_type = period_type.lower() if period_type else 'all_time'

    if period_type == 'daily':
        start_date = today
        end_date = today
    elif period_type == 'weekly':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period_type == 'monthly':
        start_date = today.replace(day=1)
        next_month_date = start_date.replace(day=28) + timedelta(days=4)
        end_date = next_month_date - timedelta(days=next_month_date.day)
    elif period_type == 'custom':
        if not start_date_str or not end_date_str:
            raise ValueError("Maxsus davr uchun 'start_date' va 'end_date' majburiy.")
        try:
            start_date = date.fromisoformat(start_date_str)
            end_date = date.fromisoformat(end_date_str)
            if start_date > end_date:
                raise ValueError("Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas.")
        except ValueError as e:
            raise ValueError(f"Sana formatida xatolik (YYYY-MM-DD): {e}")
    elif period_type == 'all_time':
        start_date = None
        end_date = today
    else:
        raise ValueError(f"Noto'g'ri 'period_type' qiymati: {period_type}.")
    return start_date, end_date


# --- Kassa Balansini Hisoblash (UZS da deb faraz qilamiz) ---
def get_kassa_balance(kassa_id):
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


# --- Dashboard uchun statistika ---
def get_dashboard_stats(kassa_id=None, period_type='all'):
    today = timezone.now().date()
    results = {}
    base_sales_filter = Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])

    if period_type == 'daily' or period_type == 'all':
        sales_uzs_today_q = Sale.objects.filter(
            base_sales_filter & Q(currency=Sale.SaleCurrency.UZS) & Q(created_at__date=today))
        uzs_today_agg = sales_uzs_today_q.aggregate(total=Sum('total_amount_currency', default=Decimal(0)),
                                                    count=Count('id'))
        results['today_sales_uzs'] = uzs_today_agg.get('total') or Decimal(0)
        results['today_sales_uzs_count'] = uzs_today_agg.get('count') or 0
        sales_usd_today_q = Sale.objects.filter(
            base_sales_filter & Q(currency=Sale.SaleCurrency.USD) & Q(created_at__date=today))
        usd_today_agg = sales_usd_today_q.aggregate(total=Sum('total_amount_currency', default=Decimal(0)),
                                                    count=Count('id'))
        results['today_sales_usd'] = usd_today_agg.get('total') or Decimal(0)
        results['today_sales_usd_count'] = usd_today_agg.get('count') or 0

    if period_type == 'monthly' or period_type == 'all':
        start_of_month = today.replace(day=1)
        sales_uzs_month_q = Sale.objects.filter(
            base_sales_filter & Q(currency=Sale.SaleCurrency.UZS) & Q(created_at__date__gte=start_of_month))
        uzs_month_agg = sales_uzs_month_q.aggregate(total=Sum('total_amount_currency', default=Decimal(0)),
                                                    count=Count('id'))
        results['monthly_sales_uzs'] = uzs_month_agg.get('total') or Decimal(0)
        results['monthly_sales_uzs_count'] = uzs_month_agg.get('count') or 0
        sales_usd_month_q = Sale.objects.filter(
            base_sales_filter & Q(currency=Sale.SaleCurrency.USD) & Q(created_at__date__gte=start_of_month))
        usd_month_agg = sales_usd_month_q.aggregate(total=Sum('total_amount_currency', default=Decimal(0)),
                                                    count=Count('id'))
        results['monthly_sales_usd'] = usd_month_agg.get('total') or Decimal(0)
        results['monthly_sales_usd_count'] = usd_month_agg.get('count') or 0

    if period_type == 'all':
        results['total_products'] = Product.objects.filter(is_active=True).count()
        results['low_stock_products'] = ProductStock.objects.filter(quantity__lte=F('minimum_stock_level')).count()
        results['total_customers'] = Customer.objects.count()
        results['new_customers_today'] = Customer.objects.filter(created_at__date=today).count()
        weekly_sales_data_uzs = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            daily_sales_uzs = Sale.objects.filter(
                base_sales_filter & Q(currency=Sale.SaleCurrency.UZS) & Q(created_at__date=day)) \
                .aggregate(daily_total=Sum('total_amount_currency', default=Decimal(0)))
            weekly_sales_data_uzs.append(
                {'day': day.strftime('%Y-%m-%d'), 'daily_total': daily_sales_uzs.get('daily_total') or Decimal(0)})
        results['weekly_sales_chart_uzs'] = weekly_sales_data_uzs
        thirty_days_ago = today - timedelta(days=30)
        top_products = SaleItem.objects.filter(
            sale__created_at__date__gte=thirty_days_ago,
            sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]
        ).values('product__name') \
                           .annotate(total_quantity_sold=Sum('quantity')).order_by('-total_quantity_sold')[:5]
        results['top_products_chart'] = list(top_products)

    if kassa_id:
        results['kassa_balance_uzs'] = get_kassa_balance(kassa_id)
        try:
            results['kassa_name'] = Kassa.objects.get(pk=kassa_id).name
        except Kassa.DoesNotExist:
            results['kassa_name'] = None
    else:
        results['kassa_balance_uzs'] = None
        results['kassa_name'] = None
    return results


# --- Sotuvlar Hisoboti ---
def get_sales_report_data(period_type, currency, start_date_str=None, end_date_str=None, seller_id=None, kassa_id=None,
                          payment_type=None, group_by=None):
    start_date, end_date = get_date_range_from_period(period_type, start_date_str, end_date_str)
    if currency not in Sale.SaleCurrency.values:
        raise ValueError(f"Noto'g'ri valyuta: {currency}. Mumkin bo'lganlar: {Sale.SaleCurrency.labels}")

    filters = Q(currency=currency) & Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])
    if start_date: filters &= Q(created_at__date__gte=start_date)
    if end_date: filters &= Q(created_at__date__lte=end_date)
    if seller_id: filters &= Q(seller_id=seller_id)
    if kassa_id: filters &= Q(kassa_id=kassa_id)
    if payment_type: filters &= Q(payment_type=payment_type)

    sales_qs = Sale.objects.filter(filters)
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
        chart_data_query = sales_qs.annotate(period=trunc_func('created_at')).values('period') \
            .annotate(period_total=Sum('total_amount_currency', default=Decimal(0))).order_by('period')
        chart_data = [{'period': item['period'].strftime(date_format), 'total': item.get('period_total') or Decimal(0)}
                      for item in chart_data_query]

    details_query = sales_qs.select_related('seller', 'customer', 'kassa').annotate(items_count=Count('items')) \
        .values('id', 'created_at', 'seller__username', 'customer__full_name',
                'kassa__name', 'payment_type', 'total_amount_currency', 'items_count').order_by('-created_at')
    details = [{'created_at': item['created_at'].strftime('%Y-%m-%d %H:%M:%S'), **item} for item in details_query]

    return {'total': total_sum, 'currency': currency, 'details': details, 'chart_data': chart_data,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None}


# --- Mahsulotlar Hisoboti ---
def get_products_report_data(period_type, currency, start_date_str=None, end_date_str=None, category_id=None):
    start_date, end_date = get_date_range_from_period(period_type, start_date_str, end_date_str)
    if currency not in Sale.SaleCurrency.values: raise ValueError(f"Noto'g'ri valyuta: {currency}.")

    filters = Q(sale__currency=currency) & Q(
        sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])
    if start_date: filters &= Q(sale__created_at__date__gte=start_date)
    if end_date: filters &= Q(sale__created_at__date__lte=end_date)
    if category_id: filters &= Q(product__category_id=category_id)

    sale_items_qs = SaleItem.objects.filter(filters).select_related('product', 'product__category', 'sale')
    price_field_expression = Case(
        When(sale__currency=Sale.SaleCurrency.UZS, then=F('price_at_sale_uzs')),
        When(sale__currency=Sale.SaleCurrency.USD, then=F('price_at_sale_usd')),
        default=Value(Decimal(0)), output_field=DecimalField(decimal_places=2)
    )
    product_summary = sale_items_qs.values('product_id', 'product__name', 'product__category__name') \
        .annotate(total_quantity=Sum('quantity', default=0),
                  total_amount=Sum(F('quantity') * price_field_expression, output_field=DecimalField(decimal_places=2),
                                   default=Decimal(0))) \
        .order_by('-total_amount')

    grand_total_sales_amount = product_summary.aggregate(grand_total=Sum('total_amount', default=Decimal(0))).get(
        'grand_total') or Decimal(0)
    pie_chart_data = []
    if grand_total_sales_amount > 0:
        pie_chart_data = [{'product_name': p['product__name'],
                           'percentage': float(round((p['total_amount'] / grand_total_sales_amount) * 100, 2)) if p.get(
                               'total_amount') else 0.0
                           } for p in product_summary if p.get('total_amount')]
    return {'currency': currency, 'table_data': list(product_summary), 'pie_chart_data': pie_chart_data,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None}


# --- Sotuvchilar Hisoboti ---
def get_sellers_report_data(period_type, currency, start_date_str=None, end_date_str=None):
    start_date, end_date = get_date_range_from_period(period_type, start_date_str, end_date_str)
    if currency not in Sale.SaleCurrency.values: raise ValueError(f"Noto'g'ri valyuta: {currency}.")

    filters = Q(currency=currency) & Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & Q(
        seller__isnull=False)
    if start_date: filters &= Q(created_at__date__gte=start_date)
    if end_date: filters &= Q(created_at__date__lte=end_date)

    sales_qs = Sale.objects.filter(filters).select_related('seller', 'seller__profile')
    seller_summary_qs = sales_qs.values('seller_id', 'seller__username', 'seller__profile__full_name') \
        .annotate(total_sales_amount_currency=Sum('total_amount_currency', default=Decimal(0)),
                  total_sales_count=Count('id', default=0)).order_by('-total_sales_amount_currency')

    report_list = []
    for summary in seller_summary_qs:
        seller_id = summary['seller_id']
        # Sotilgan mahsulotlar sonini hisoblash (shu sotuvchi uchun, shu davrda, shu valyutada)
        items_sold_count = SaleItem.objects.filter(
            sale__seller_id=seller_id,
            sale__currency=currency,
            sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED],
            sale__created_at__date__gte=start_date if start_date else date.min,  # Agar start_date None bo'lsa
            sale__created_at__date__lte=end_date if end_date else date.max  # Agar end_date None bo'lsa
        ).aggregate(total_items=Sum('quantity', default=0))['total_items']

        report_list.append({
            'seller_id': seller_id,
            'username': summary['seller__username'],
            'full_name': summary['seller__profile__full_name'],
            'total_sales_amount_currency': summary.get('total_sales_amount_currency') or Decimal(0),
            'total_sales_count': summary.get('total_sales_count') or 0,
            'total_items_sold': items_sold_count or 0
        })
    return {'currency': currency, 'table_data': report_list,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None}


# --- Nasiyalar Hisoboti ---
def get_installments_report_data(period_type, start_date_str=None, end_date_str=None, customer_id=None, status=None,
                                 currency_filter=None):
    start_date, end_date = get_date_range_from_period(period_type, start_date_str, end_date_str)
    filters = Q()
    if start_date: filters &= Q(created_at__date__gte=start_date)
    if end_date: filters &= Q(created_at__date__lte=end_date)
    if customer_id: filters &= Q(customer_id=customer_id)
    if status: filters &= Q(status=status)
    if currency_filter and currency_filter in Sale.SaleCurrency.values:
        filters &= Q(currency=currency_filter)

    plans_qs = InstallmentPlan.objects.filter(filters).select_related('customer', 'sale')
    remaining_expression = Cast(F('total_amount_due') - F('return_adjustment') - F('amount_paid'),
                                output_field=DecimalField(decimal_places=2))
    report_values = plans_qs.annotate(remaining_final=remaining_expression) \
        .values('id', 'sale_id', 'currency', 'customer__full_name', 'customer__phone_number',
                'initial_amount', 'interest_rate', 'term_months', 'monthly_payment',
                'total_amount_due', 'down_payment', 'amount_paid', 'remaining_final',  # 'remaining' o'rniga
                'status', 'created_at').order_by('-created_at')

    report_list = []
    for plan_data in report_values:
        try:
            plan_instance = InstallmentPlan.objects.prefetch_related('schedule').get(
                pk=plan_data['id'])  # schedule ni prefetch qilish
            next_due_date = plan_instance.get_next_payment_due_date
            is_overdue_val = plan_instance.is_overdue()
        except InstallmentPlan.DoesNotExist:
            next_due_date = None;
            is_overdue_val = False
        report_list.append({
            **plan_data,
            'next_payment_due_date': next_due_date.strftime('%Y-%m-%d') if next_due_date else None,
            'is_overdue': is_overdue_val,
            'status_display': InstallmentPlan.PlanStatus(plan_data.get('status')).label if plan_data.get(
                'status') else None,
            'created_at': plan_data['created_at'].strftime('%Y-%m-%d %H:%M:%S') if plan_data.get(
                'created_at') else None,
            'remaining_amount': plan_data.get('remaining_final') or Decimal(0)  # Nomini moslashtirdim
        })
    return {'data': report_list,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None}


# --- Ombor Hisobotlari ---
def get_inventory_stock_report(kassa_id=None, category_id=None, low_stock_only=False):
    filters = Q()
    if kassa_id: filters &= Q(kassa_id=kassa_id)
    if category_id: filters &= Q(product__category_id=category_id)
    if low_stock_only: filters &= Q(quantity__lte=F('minimum_stock_level'))
    stocks = ProductStock.objects.filter(filters).select_related('product__category', 'kassa').order_by('kassa__name',
                                                                                                        'product__name')
    report_data = []
    for stock in stocks:
        report_data.append({
            'product_id': stock.product_id, 'product_name': stock.product.name, 'barcode': stock.product.barcode,
            'category_name': stock.product.category.name if stock.product.category else None,
            'kassa_id': stock.kassa_id, 'kassa_name': stock.kassa.name,
            'quantity': stock.quantity, 'minimum_stock_level': stock.minimum_stock_level,
            'is_low_stock': stock.is_low_stock, 'price_uzs': stock.product.price_uzs,
            'price_usd': stock.product.price_usd,
        })
    return report_data


def get_inventory_history_report(period_type, start_date_str=None, end_date_str=None, kassa_id=None, product_id=None,
                                 user_id=None, operation_type=None):
    start_date, end_date = get_date_range_from_period(period_type, start_date_str, end_date_str)
    filters = Q()
    if start_date: filters &= Q(timestamp__date__gte=start_date)
    if end_date: filters &= Q(timestamp__date__lte=end_date)
    if kassa_id: filters &= Q(kassa_id=kassa_id)
    if product_id: filters &= Q(product_id=product_id)
    if user_id: filters &= Q(user_id=user_id)
    if operation_type: filters &= Q(operation_type=operation_type)
    operations = InventoryOperation.objects.filter(filters).select_related('product', 'kassa',
                                                                           'user__profile').order_by('-timestamp')
    report_data = []
    for op in operations:
        report_data.append({
            'id': op.id, 'timestamp': op.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'product_name': op.product.name, 'kassa_name': op.kassa.name, 'quantity': op.quantity,
            'operation_type': op.operation_type, 'operation_type_display': op.get_operation_type_display(),
            'user_username': op.user.username if op.user else None,
            'user_full_name': op.user.profile.full_name if op.user and hasattr(op.user, 'profile') else None,
            'comment': op.comment,
        })
    return {'data': report_data,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None}