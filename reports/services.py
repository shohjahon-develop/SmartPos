# reports/services.py
import calendar

from django.db.models import Sum, Count, F, DecimalField, Q, Value, Case, When
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, Cast
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal

# Model importlari
from users.models import User, UserProfile
from sales.models import Sale, SaleItem, Customer, KassaTransaction, Kassa  # SaleCurrency endi Sale orqali olinadi
from products.models import Product, Category
from inventory.models import ProductStock, InventoryOperation
from installments.models import InstallmentPlan, InstallmentPayment

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


# --- YORDAMCHI FUNKSIYA: DAVR BO'YICHA SANA ORALIG'INI OLISH (O'zgarishsiz) ---
def get_date_range_from_period(period_type, start_date_str=None, end_date_str=None):
    # ... (avvalgi kod) ...
    today = timezone.now().date()
    start_date, end_date = None, None
    period_type = period_type.lower() if period_type else 'all_time' # yoki 'monthly' default
    if period_type == 'daily':
        start_date = end_date = today
    elif period_type == 'weekly':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period_type == 'monthly':
        start_date = today.replace(day=1)
        # Oyning oxirgi kunini to'g'ri topish
        _, last_day_of_month = calendar.monthrange(today.year, today.month)
        end_date = today.replace(day=last_day_of_month)
    elif period_type == 'custom':
        if not start_date_str or not end_date_str: raise ValueError("Custom uchun 'start_date'/'end_date' majburiy.")
        try:
            start_date, end_date = date.fromisoformat(start_date_str), date.fromisoformat(end_date_str)
        except ValueError as e:
            raise ValueError(f"Sana formati xato (YYYY-MM-DD): {e}")
        if start_date > end_date: raise ValueError("Boshlanish sanasi tugashdan keyin.")
    elif period_type == 'all_time':
        end_date = today
    else: # Default 'monthly' yoki xatolik
        # Agar notanish period_type kelsa, default 'monthly' ni ishlatamiz yoki xatolik beramiz
        # Hozircha xatolik beramiz, chunki sales_chart uchun aniq periodlar kerak
        raise ValueError(f"Noto'g'ri 'period_type': {period_type}. Mumkin: 'daily', 'weekly', 'monthly'.")
    return start_date, end_date


# --- Kassa Balansini Hisoblash (UZS da deb faraz qilamiz) (O'zgarishsiz) ---
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


# --- Dashboard uchun statistika (YANGI FOYDA LOGIKASI BILAN) ---
def get_dashboard_stats(kassa_id=None, period_type='all'):
    today = timezone.now().date()
    results = {}
    base_sales_filter = Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])
    kassa_q_filter_for_sale = Q(kassa_id=kassa_id) if kassa_id else Q()
    # Nasiya to'lovlari uchun kassa filtri plan.sale.kassa orqali bo'ladi
    kassa_q_filter_for_installment = Q(plan__sale__kassa_id=kassa_id) if kassa_id else Q()

    # Kunlik Statistikalar
    daily_profit_uzs, daily_profit_usd = Decimal(0), Decimal(0)
    daily_sales_uzs_count, daily_sales_usd_count = 0, 0

    if period_type == 'daily' or period_type == 'all':
        # Sotuvdan tushgan UZS (kunlik)
        s_uzs_today_paid = Sale.objects.filter(
            base_sales_filter & kassa_q_filter_for_sale & Q(currency=Sale.SaleCurrency.UZS) & Q(created_at__date=today)
        ).aggregate(paid=Sum('amount_actually_paid_at_sale', default=Decimal(0)))['paid'] or Decimal(0)
        daily_sales_uzs_count = Sale.objects.filter(
            base_sales_filter & kassa_q_filter_for_sale & Q(currency=Sale.SaleCurrency.UZS) & Q(created_at__date=today)
        ).count()

        # Sotuvdan tushgan USD (kunlik)
        s_usd_today_paid = Sale.objects.filter(
            base_sales_filter & kassa_q_filter_for_sale & Q(currency=Sale.SaleCurrency.USD) & Q(created_at__date=today)
        ).aggregate(paid=Sum('amount_actually_paid_at_sale', default=Decimal(0)))['paid'] or Decimal(0)
        daily_sales_usd_count = Sale.objects.filter(
            base_sales_filter & kassa_q_filter_for_sale & Q(currency=Sale.SaleCurrency.USD) & Q(created_at__date=today)
        ).count()

        # Nasiyadan tushgan UZS (kunlik)
        i_uzs_today_paid = InstallmentPayment.objects.filter(
            kassa_q_filter_for_installment & Q(plan__currency=Sale.SaleCurrency.UZS) & Q(payment_date__date=today)
        ).aggregate(paid=Sum('amount', default=Decimal(0)))['paid'] or Decimal(0)

        # Nasiyadan tushgan USD (kunlik)
        i_usd_today_paid = InstallmentPayment.objects.filter(
            kassa_q_filter_for_installment & Q(plan__currency=Sale.SaleCurrency.USD) & Q(payment_date__date=today)
        ).aggregate(paid=Sum('amount', default=Decimal(0)))['paid'] or Decimal(0)

        daily_profit_uzs = s_uzs_today_paid + i_uzs_today_paid
        daily_profit_usd = s_usd_today_paid + i_usd_today_paid

        results['today_profit_uzs'] = daily_profit_uzs
        results['today_sales_uzs_count'] = daily_sales_uzs_count
        results['today_profit_usd'] = daily_profit_usd
        results['today_sales_usd_count'] = daily_sales_usd_count

    # Oylik Statistikalar
    monthly_profit_uzs, monthly_profit_usd = Decimal(0), Decimal(0)
    monthly_sales_uzs_count, monthly_sales_usd_count = 0, 0

    if period_type == 'monthly' or period_type == 'all':
        start_of_month = today.replace(day=1)
        s_uzs_month_paid = Sale.objects.filter(
            base_sales_filter & kassa_q_filter_for_sale & Q(currency=Sale.SaleCurrency.UZS) & Q(
                created_at__date__gte=start_of_month)
        ).aggregate(paid=Sum('amount_actually_paid_at_sale', default=Decimal(0)))['paid'] or Decimal(0)
        monthly_sales_uzs_count = Sale.objects.filter(
            base_sales_filter & kassa_q_filter_for_sale & Q(currency=Sale.SaleCurrency.UZS) & Q(
                created_at__date__gte=start_of_month)
        ).count()

        s_usd_month_paid = Sale.objects.filter(
            base_sales_filter & kassa_q_filter_for_sale & Q(currency=Sale.SaleCurrency.USD) & Q(
                created_at__date__gte=start_of_month)
        ).aggregate(paid=Sum('amount_actually_paid_at_sale', default=Decimal(0)))['paid'] or Decimal(0)
        monthly_sales_usd_count = Sale.objects.filter(
            base_sales_filter & kassa_q_filter_for_sale & Q(currency=Sale.SaleCurrency.USD) & Q(
                created_at__date__gte=start_of_month)
        ).count()

        i_uzs_month_paid = InstallmentPayment.objects.filter(
            kassa_q_filter_for_installment & Q(plan__currency=Sale.SaleCurrency.UZS) & Q(
                payment_date__date__gte=start_of_month)
        ).aggregate(paid=Sum('amount', default=Decimal(0)))['paid'] or Decimal(0)

        i_usd_month_paid = InstallmentPayment.objects.filter(
            kassa_q_filter_for_installment & Q(plan__currency=Sale.SaleCurrency.USD) & Q(
                payment_date__date__gte=start_of_month)
        ).aggregate(paid=Sum('amount', default=Decimal(0)))['paid'] or Decimal(0)

        monthly_profit_uzs = s_uzs_month_paid + i_uzs_month_paid
        monthly_profit_usd = s_usd_month_paid + i_usd_month_paid

        results['monthly_profit_uzs'] = monthly_profit_uzs
        results['monthly_sales_uzs_count'] = monthly_sales_uzs_count
        results['monthly_profit_usd'] = monthly_profit_usd
        results['monthly_sales_usd_count'] = monthly_sales_usd_count

    if period_type == 'all':  # Umumiy statistikalar (faqat 'all' uchun yoki har doim)
        results['total_products'] = Product.objects.filter(is_active=True).count()
        results['low_stock_products'] = ProductStock.objects.filter(quantity__lte=F('minimum_stock_level')).count()
        results['total_customers'] = Customer.objects.count()
        results['new_customers_today'] = Customer.objects.filter(created_at__date=today).count()

        weekly_sales_data_uzs = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_s_paid = Sale.objects.filter(
                base_sales_filter & kassa_q_filter_for_sale & Q(currency=Sale.SaleCurrency.UZS) & Q(
                    created_at__date=day)).aggregate(paid=Sum('amount_actually_paid_at_sale', default=Decimal(0)))[
                             'paid'] or Decimal(0)
            day_i_paid = InstallmentPayment.objects.filter(
                kassa_q_filter_for_installment & Q(plan__currency=Sale.SaleCurrency.UZS) & Q(
                    payment_date__date=day)).aggregate(paid=Sum('amount', default=Decimal(0)))['paid'] or Decimal(0)
            weekly_sales_data_uzs.append(
                {'day': day.strftime('%Y-%m-%d'), 'daily_total_profit': day_s_paid + day_i_paid})
        results['weekly_sales_chart_uzs'] = weekly_sales_data_uzs

        thirty_days_ago = today - timedelta(days=30)
        top_products = SaleItem.objects.filter(sale__created_at__date__gte=thirty_days_ago,
                                               sale__status__in=[Sale.SaleStatus.COMPLETED,
                                                                 Sale.SaleStatus.PARTIALLY_RETURNED]).values(
            'product__name').annotate(total_quantity_sold=Sum('quantity')).order_by('-total_quantity_sold')[:5]
        results['top_products_chart'] = list(top_products)

    if kassa_id:
        results['kassa_balance_uzs'] = get_kassa_balance(kassa_id)  # Bu faqat UZS kassasi uchun
        try:
            results['kassa_name'] = Kassa.objects.get(pk=kassa_id).name
        except Kassa.DoesNotExist:
            results['kassa_name'] = None
    else:
        results['kassa_balance_uzs'] = None;
        results['kassa_name'] = None
    return results


# --- Sotuvlar Hisoboti (Foyda `amount_actually_paid_at_sale` dan) ---
def get_sales_report_data(period_type='daily', start_date_str=None, end_date_str=None,
                          currency='UZS', seller_id=None, kassa_id=None,
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

    # "Foyda" ni hisoblash (kassaga tushgan pul)
    total_profit_in_currency = sales_qs.aggregate(
        total_profit=Sum('amount_actually_paid_at_sale', default=Decimal(0))
    )['total_profit'] or Decimal(0)

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
            .annotate(period_profit=Sum('amount_actually_paid_at_sale', default=Decimal(0))).order_by('period')
        chart_data = [
            {'period': item['period'].strftime(date_format), 'total_profit': item.get('period_profit') or Decimal(0)}
            for item in chart_data_query]

    details_query = sales_qs.select_related('seller', 'customer', 'kassa').annotate(items_count=Count('items')) \
        .values('id', 'created_at', 'seller__username', 'customer__full_name',
                'kassa__name', 'payment_type',
                'original_total_amount_currency',  # Asl summa
                'final_amount_currency',  # Chegirma bilan summa
                'amount_actually_paid_at_sale',  # Haqiqatda to'langan
                'currency', 'items_count').order_by('-created_at')
    details = []
    for item in details_query:
        detail_item = item.copy()
        detail_item['created_at'] = item['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        details.append(detail_item)

    return {'total_profit': total_profit_in_currency, 'currency': currency, 'details': details,
            'chart_data': chart_data,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None}


# --- Mahsulotlar Hisoboti (Narx `price_at_sale_currency` dan, bu yakuniy narx) ---
def get_products_report_data(period_type='monthly', start_date_str=None, end_date_str=None,
                             currency='UZS', category_id=None):
    start_date, end_date = get_date_range_from_period(period_type, start_date_str, end_date_str)
    if currency not in Sale.SaleCurrency.values: raise ValueError(f"Noto'g'ri valyuta: {currency}.")

    filters = Q(sale__currency=currency) & Q(
        sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])
    if start_date: filters &= Q(sale__created_at__date__gte=start_date)
    if end_date: filters &= Q(sale__created_at__date__lte=end_date)
    if category_id: filters &= Q(product__category_id=category_id)

    sale_items_qs = SaleItem.objects.filter(filters).select_related('product', 'product__category', 'sale')

    # Bu yerda SaleItem.price_at_sale_currency ni ishlatamiz, chunki u chegirma qilingan narx
    product_summary = sale_items_qs.values('product_id', 'product__name', 'product__category__name') \
        .annotate(total_quantity=Sum('quantity', default=0),
                  total_sold_amount=Sum(F('quantity') * F('price_at_sale_currency'),
                                        output_field=DecimalField(decimal_places=2), default=Decimal(0))) \
        .order_by('-total_sold_amount')  # Yakuniy sotilgan summa bo'yicha

    grand_total_sold_amount = product_summary.aggregate(grand_total=Sum('total_sold_amount', default=Decimal(0))).get(
        'grand_total') or Decimal(0)
    pie_chart_data = []
    if grand_total_sold_amount > 0:
        pie_chart_data = [{'product_name': p['product__name'],
                           'percentage': float(
                               round((p['total_sold_amount'] / grand_total_sold_amount) * 100, 2)) if p.get(
                               'total_sold_amount') else 0.0
                           } for p in product_summary if p.get('total_sold_amount')]
    return {'currency': currency, 'table_data': list(product_summary), 'pie_chart_data': pie_chart_data,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None}


# --- Sotuvchilar Hisoboti (Foyda `amount_actually_paid_at_sale` dan) ---
def get_sellers_report_data(period_type='monthly', start_date_str=None, end_date_str=None,
                            currency='UZS'):
    start_date, end_date = get_date_range_from_period(period_type, start_date_str, end_date_str)
    if currency not in Sale.SaleCurrency.values: raise ValueError(f"Noto'g'ri valyuta: {currency}.")

    filters = Q(currency=currency) & Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & Q(
        seller__isnull=False)
    if start_date: filters &= Q(created_at__date__gte=start_date)
    if end_date: filters &= Q(created_at__date__lte=end_date)

    sales_qs = Sale.objects.filter(filters).select_related('seller', 'seller__profile')

    seller_summary_qs = sales_qs.values('seller_id', 'seller__username', 'seller__profile__full_name') \
        .annotate(total_profit_by_seller=Sum('amount_actually_paid_at_sale', default=Decimal(0)),
                  total_sales_count=Count('id', default=0)).order_by('-total_profit_by_seller')

    report_list = []
    for summary in seller_summary_qs:
        seller_id = summary['seller_id']
        # Sotilgan mahsulotlar soni (shu sotuvchi, davr, valyuta)
        items_sold_count_agg = SaleItem.objects.filter(
            sale__seller_id=seller_id, sale__currency=currency,
            sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED],
            sale__created_at__date__gte=(start_date if start_date else date.min),
            sale__created_at__date__lte=(end_date if end_date else date.max)
        ).aggregate(total_items=Sum('quantity', default=0))
        items_sold_count = items_sold_count_agg.get('total_items') or 0

        report_list.append({
            'seller_id': seller_id, 'username': summary['seller__username'],
            'full_name': summary['seller__profile__full_name'],
            'total_profit_by_seller': summary.get('total_profit_by_seller') or Decimal(0),
            'total_sales_count': summary.get('total_sales_count') or 0,
            'total_items_sold': items_sold_count
        })
    return {'currency': currency, 'table_data': report_list,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None}


# --- Nasiyalar Hisoboti (O'zgarishsiz qolishi mumkin, chunki u o'z valyutasida) ---
def get_installments_report_data(period_type='all_time', start_date_str=None, end_date_str=None,
                                 customer_id=None, status=None, currency_filter=None):
    # ... (Bu funksiya avvalgi javobdagi kabi to'liq va o'zgarishsiz qoladi) ...
    # Faqat SaleCurrency ni to'g'ri import qilish kerak.
    start_date, end_date = get_date_range_from_period(period_type, start_date_str, end_date_str)
    filters = Q()
    if start_date: filters &= Q(created_at__date__gte=start_date)
    if end_date: filters &= Q(created_at__date__lte=end_date)
    if customer_id:
        try:
            filters &= Q(customer_id=int(customer_id))
        except ValueError:
            raise ValueError(f"Noto'g'ri customer_id formati: {customer_id}")
    if status:
        if status not in InstallmentPlan.PlanStatus.values: raise ValueError(f"Noto'g'ri nasiya holati: {status}")
        filters &= Q(status=status)
    if currency_filter and currency_filter in Sale.SaleCurrency.values: filters &= Q(currency=currency_filter)
    plans_qs = InstallmentPlan.objects.filter(filters).select_related('customer', 'sale')
    remaining_expression = Cast(F('total_amount_due') - F('return_adjustment') - F('amount_paid'),
                                output_field=DecimalField(decimal_places=2))
    report_values = plans_qs.annotate(remaining_final=remaining_expression) \
        .values('id', 'sale_id', 'currency', 'customer__full_name', 'customer__phone_number',
                'initial_amount', 'interest_rate', 'term_months', 'monthly_payment',
                'total_amount_due', 'down_payment', 'amount_paid', 'remaining_final',
                'status', 'created_at').order_by('-created_at')
    report_list = []
    for plan_data in report_values:
        try:
            plan_instance = InstallmentPlan.objects.prefetch_related('schedule').get(pk=plan_data['id'])
            next_due_date = plan_instance.get_next_payment_due_date
            is_overdue_val = plan_instance.is_overdue()
        except InstallmentPlan.DoesNotExist:
            next_due_date, is_overdue_val = None, False
        report_list.append({
            **plan_data,
            'next_payment_due_date': next_due_date.strftime('%Y-%m-%d') if next_due_date else None,
            'is_overdue': is_overdue_val,
            'status_display': InstallmentPlan.PlanStatus(plan_data.get('status')).label if plan_data.get(
                'status') else None,
            'created_at': plan_data['created_at'].strftime('%Y-%m-%d %H:%M:%S') if plan_data.get(
                'created_at') else None,
            'remaining_amount': plan_data.get('remaining_final') or Decimal(0)
        })
    return {'data': report_list,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None,
            'period_type': period_type}


# --- Ombor Hisobotlari (O'zgarishsiz) ---
def get_inventory_stock_report(kassa_id=None, category_id=None, low_stock_only=False):
    # ... (avvalgi kod) ...
    filters = Q()
    if kassa_id: filters &= Q(kassa_id=kassa_id)
    if category_id: filters &= Q(product__category_id=category_id)
    if low_stock_only: filters &= Q(quantity__lte=F('minimum_stock_level'))
    stocks = ProductStock.objects.filter(filters).select_related('product__category', 'kassa', 'product').order_by(
        'kassa__name', 'product__name')
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


def get_inventory_history_report(period_type='daily', start_date_str=None, end_date_str=None, kassa_id=None,
                                 product_id=None, user_id=None, operation_type=None):
    # ... (avvalgi kod) ...
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


# YANGI FUNKSIYA: Sotuvlar grafigi uchun ma'lumotlarni tayyorlash
def get_sales_chart_data(period_type='monthly', currency='UZS', kassa_id=None):
    """
    Sotuvlar grafigi uchun ma'lumotlarni tayyorlaydi.
    'period_type' (daily, weekly, monthly) va 'currency' (UZS, USD) bo'yicha.
    Natijada 'labels' va 'data' massivlarini qaytaradi.
    """
    today = timezone.now().date()
    target_currency = currency.upper()
    if target_currency not in Sale.SaleCurrency.values:
        raise ValueError(f"Noto'g'ri valyuta: {target_currency}. Mumkin: {Sale.SaleCurrency.labels}")

    period_type = period_type.lower()
    group_by_func = None
    label_format = ""
    date_range_start, date_range_end = None, None
    all_labels_in_period = []  # Barcha mumkin bo'lgan labellarni saqlash uchun

    base_sales_filter = Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & \
                        Q(currency=target_currency)
    base_installments_filter = Q(plan__currency=target_currency)  # Nasiya to'lovlari uchun

    if kassa_id:
        try:
            kassa_id = int(kassa_id)
            base_sales_filter &= Q(kassa_id=kassa_id)
            base_installments_filter &= Q(plan__sale__kassa_id=kassa_id)
        except ValueError:
            raise ValueError("Noto'g'ri kassa_id formati.")

    if period_type == 'daily':  # Joriy kun (hozircha faqat bitta nuqta qaytaradi, ko'p kunlik uchun 'weekly' yoki 'monthly' yaxshiroq)
        # Yoki o'tgan X kun uchun qilish mumkin. Hozircha soddalik uchun joriy kun.
        # Agar 'daily' o'tgan 7 kunni anglatsa, logikani o'zgartirish kerak.
        # Keling, 'daily' ni o'tgan 7 kun deb qabul qilaylik, grafik uchun qulayroq.
        date_range_end = today
        date_range_start = today - timedelta(days=6)
        group_by_func = TruncDay
        label_format = '%Y-%m-%d'
        current_day = date_range_start
        while current_day <= date_range_end:
            all_labels_in_period.append(current_day.strftime(label_format))
            current_day += timedelta(days=1)

    elif period_type == 'weekly':  # Joriy hafta (kunlar bo'yicha)
        # Yoki o'tgan 4 hafta? Hozircha joriy haftaning kunlari.
        # Keling, o'tgan 4 haftani olaylik (har bir hafta bitta nuqta)
        date_range_end = today
        date_range_start = today - timedelta(weeks=3)  # Joriy hafta + oldingi 3 hafta
        group_by_func = TruncWeek  # Haftalar bo'yicha guruhlaymiz
        label_format = '%Y / W%W'  # Yil / Hafta raqami

        current_week_start = date_range_start - timedelta(days=date_range_start.weekday())
        while current_week_start <= date_range_end:
            all_labels_in_period.append(current_week_start.strftime(label_format))
            current_week_start += timedelta(weeks=1)


    elif period_type == 'monthly':  # Joriy oy (kunlar bo'yicha)
        # Yoki o'tgan X oy? Hozircha joriy oyning kunlari.
        # Keling, joriy oyning kunlarini olaylik
        date_range_start = today.replace(day=1)
        _, last_day_of_month = calendar.monthrange(today.year, today.month)
        date_range_end = today.replace(day=last_day_of_month)
        group_by_func = TruncDay  # Kunlar bo'yicha guruhlaymiz
        label_format = '%Y-%m-%d'
        current_day = date_range_start
        while current_day <= date_range_end:
            all_labels_in_period.append(current_day.strftime(label_format))
            current_day += timedelta(days=1)

    else:
        raise ValueError(f"Noto'g'ri 'period_type': {period_type}. Mumkin: 'daily', 'weekly', 'monthly'.")

    # Sotuvlardan tushgan pul
    sales_data = Sale.objects.filter(
        base_sales_filter & Q(created_at__date__gte=date_range_start) & Q(created_at__date__lte=date_range_end)) \
        .annotate(period_group=group_by_func('created_at')) \
        .values('period_group') \
        .annotate(total=Sum('amount_actually_paid_at_sale', default=Decimal(0))) \
        .order_by('period_group')

    # Nasiyalardan tushgan pul
    installments_data = InstallmentPayment.objects.filter(
        base_installments_filter & Q(payment_date__date__gte=date_range_start) & Q(
            payment_date__date__lte=date_range_end)) \
        .annotate(period_group=group_by_func('payment_date')) \
        .values('period_group') \
        .annotate(total=Sum('amount', default=Decimal(0))) \
        .order_by('period_group')

    # Natijalarni birlashtirish
    aggregated_data = {}  # {'2023-05-01': Decimal('100.00'), ...}

    for item in sales_data:
        if item['period_group']:  # None bo'lmasligi kerak
            period_label = item['period_group'].strftime(label_format)
            aggregated_data[period_label] = aggregated_data.get(period_label, Decimal(0)) + (
                        item['total'] or Decimal(0))

    for item in installments_data:
        if item['period_group']:
            period_label = item['period_group'].strftime(label_format)
            aggregated_data[period_label] = aggregated_data.get(period_label, Decimal(0)) + (
                        item['total'] or Decimal(0))

    # Grafik uchun 'labels' va 'data' tayyorlash
    # all_labels_in_period bo'yicha yurib, aggregated_data dan qiymat olish
    chart_labels = all_labels_in_period
    chart_values = [aggregated_data.get(label, Decimal(0)) for label in chart_labels]

    return {
        "currency": target_currency,
        "period_type": period_type,
        "period_label_format": label_format,
        "labels": chart_labels,
        "data": chart_values,
        "debug_date_range_start": date_range_start.isoformat() if date_range_start else None,
        "debug_date_range_end": date_range_end.isoformat() if date_range_end else None,
    }