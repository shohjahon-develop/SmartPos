# reports/views.py
from rest_framework import views, status, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from django.utils.dateparse import parse_date
from django.utils import timezone
from datetime import timedelta, date # date import
from decimal import Decimal # Decimal import

from installments.models import InstallmentPlan
# --- Importlar qisqartirildi ---
from .services import (
    get_dashboard_stats, get_sales_report_data, get_products_report_data,
    get_sellers_report_data, get_installments_report_data
)
# --- Eksport bilan bog'liq importlar olib tashlandi ---
from products.models import Category, Kassa
from users.models import User, Store  # Yoki settings.AUTH_USER_MODEL

class DashboardStatsView(views.APIView):
    """Boshqaruv paneli uchun asosiy statistikalar"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if not hasattr(user, 'profile') or not user.profile.store:
            if not user.is_superuser: # Faqat superuser do'konsiz bo'lishi mumkin
                return Response({"error": "Foydalanuvchi do'konga biriktirilmagan."}, status=status.HTTP_400_BAD_REQUEST)
            # Superuser uchun qaysi do'kon statistikasini ko'rsatish kerak?
            # Yoki superuser dashboardi boshqacha bo'ladimi?
            # Hozircha xatolik qaytaramiz yoki birinchi do'konni olamiz
            return Response({"error": "Superadmin uchun dashboard logikasi aniqlanmagan."}, status=status.HTTP_400_BAD_REQUEST)

        store = user.profile.store

        # Foydalanuvchi qaysi kassani tanlaganini query parametrdan olish (frontend yuborishi kerak)
        # Masalan, agar dashboardda kassa tanlash imkoniyati bo'lsa
        kassa_id = request.query_params.get('kassa_id', None)
        # Agar kassa tanlanmagan bo'lsa, foydalanuvchi do'konidagi birinchi aktiv kassani olish
        if not kassa_id:
             first_active_kassa = Kassa.objects.filter(store=store, is_active=True).first()
             if first_active_kassa:
                 kassa_id = first_active_kassa.id
             else:
                  # Agar aktiv kassa yo'q bo'lsa, balansni hisoblab bo'lmaydi
                  kassa_id = None

        try:
            # store.id va kassa_id ni service funksiyasiga uzatish
            stats = get_dashboard_stats(store_id=store.id, kassa_id=kassa_id)
            return Response(stats)
        except Exception as e:
            print(f"Error in DashboardStatsView: {e}") # Loglash
            return Response({"error": "Dashboard ma'lumotlarini olishda xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BaseReportView(views.APIView):
    """Hisobotlar uchun umumiy logikani saqlovchi asosiy view (eksportsiz)"""
    permission_classes = [permissions.IsAuthenticated]
    required_params = ['start_date', 'end_date'] # Ba'zi hisobotlar uchun bular ixtiyoriy bo'lishi mumkin
    optional_params = ['currency']
    data_service = None # Subklasslarda aniqlanadi

    def get_store_id(self, request):
        """
        So'rov yuborayotgan foydalanuvchiga mos do'kon ID sini aniqlaydi.
        Superuser uchun 'store_id' query parametri kutiladi.
        """
        user = request.user
        if hasattr(user, 'profile') and user.profile.store:
            # Oddiy foydalanuvchi (admin, sotuvchi, ...) o'z do'koni ID sini qaytaradi
            return user.profile.store.id
        elif user.is_superuser:
            # Superuser uchun frontend 'store_id' ni query param orqali yuborishi kerak
            store_id = request.query_params.get('store_id')
            if not store_id:
                # Agar superuser store_id ni yubormasa, xatolik yoki default logika
                # Masalan, birinchi do'konni olish yoki xatolik qaytarish
                # Hozircha xatolik qaytaramiz
                raise ValueError("Superadmin uchun 'store_id' query parametri majburiy.")
            try:
                # store_id raqam ekanligini tekshirish
                store_id = int(store_id)
                # Bu store mavjudligini tekshirish
                if not Store.objects.filter(pk=store_id).exists():
                    raise ValueError(f"Ko'rsatilgan 'store_id'={store_id} bilan do'kon topilmadi.")
                return store_id
            except (ValueError, TypeError):
                 raise ValueError("Noto'g'ri 'store_id' formati.")
        else:
            # Do'konga biriktirilmagan foydalanuvchi (lekin superuser emas)
            raise PermissionDenied("Hisobotni ko'rish uchun siz do'konga biriktirilmagansiz.")

    def get(self, request):
        """
        Umumiy GET so'rovini qayta ishlaydi:
        1. Foydalanuvchi uchun do'kon ID sini aniqlaydi.
        2. Query parametrlarni (sana, valyuta va hk) oladi va validatsiya qiladi.
        3. Subklasslarda aniqlangan data_service funksiyasini chaqiradi.
        4. Natijani JSON formatida qaytaradi.
        """
        try:
            store_id = self.get_store_id(request)
            params = {'store_id': store_id} # Parametrlar dictini boshlash
        except (ValueError, PermissionDenied) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Kutilmagan xatoliklar uchun
            print(f"Error getting store_id: {e}")
            return Response({"error": "Do'konni aniqlashda noma'lum xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # --- Sanalarni olish va validatsiya ---
        # Agar hisobot uchun sanalar majburiy bo'lsa (required_params da bo'lsa)
        if 'start_date' in self.required_params or 'end_date' in self.required_params:
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')
            if not start_date_str and 'start_date' in self.required_params:
                return Response({"error": "'start_date' parametri majburiy."}, status=status.HTTP_400_BAD_REQUEST)
            if not end_date_str and 'end_date' in self.required_params:
                 return Response({"error": "'end_date' parametri majburiy."}, status=status.HTTP_400_BAD_REQUEST)

            try:
                # Agar sana berilmasa, default qiymat (masalan, bugun yoki 30 kun oldin)
                end_date = parse_date(end_date_str) if end_date_str else timezone.now().date()
                start_date = parse_date(start_date_str) if start_date_str else end_date - timedelta(days=30)
                if start_date > end_date:
                     raise ValueError("Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas.")
                params['start_date'] = start_date
                params['end_date'] = end_date
            except (ValueError, TypeError) as e:
                return Response({"error": f"Sana parametrlarida xatolik: {e}. YYYY-MM-DD formatida kiriting."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Sanalar majburiy bo'lmasa (masalan, InstallmentsReportView)
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')
            try:
                params['start_date'] = parse_date(start_date_str) if start_date_str else None
                params['end_date'] = parse_date(end_date_str) if end_date_str else None
                if params['start_date'] and params['end_date'] and params['start_date'] > params['end_date']:
                     raise ValueError("Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas.")
            except (ValueError, TypeError) as e:
                 return Response({"error": f"Sana parametrlarida xatolik: {e}. YYYY-MM-DD formatida kiriting."}, status=status.HTTP_400_BAD_REQUEST)

        # --- Valyutani olish (agar kerak bo'lsa) ---
        # Ayrim hisobotlar (masalan, Nasiya) uchun valyuta kerak emas.
        # Buni qanday boshqarish kerak? Masalan, data_service buni qabul qilmasligi mumkin.
        # Yoki BaseReportView ga 'uses_currency' flag qo'shish mumkin.
        # Hozircha, agar optional_params da bo'lsa, olamiz.
        if 'currency' in self.optional_params or 'currency' in self.required_params:
            currency = request.query_params.get('currency', 'UZS').upper()
            if currency not in ['UZS', 'USD']:
                 return Response({"error": "Valyuta faqat 'UZS' yoki 'USD' bo'lishi mumkin."}, status=status.HTTP_400_BAD_REQUEST)
            params['currency'] = currency

        # --- Qo'shimcha parametrlarni olish ---
        # Bu metod subklasslarda implementatsiya qilinadi va params dictini to'ldiradi
        try:
             self.extract_extra_params(request, params)
        except (ValidationError, ValueError) as e: # extract_extra_params ham xato berishi mumkin
             return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


        # --- Servis funksiyasini chaqirish ---
        if not self.data_service:
            # Bu dasturchi xatosi
            print("ERROR: data_service is not defined for this report view.")
            return Response({"error": "Hisobot xizmati aniqlanmagan."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            # Parametrlarni servis funksiyasiga uzatish
            report_data = self.data_service(**params)
            return Response(report_data) # To'g'ridan-to'g'ri JSON javob
        except TypeError as e:
             # Agar servis funksiyasi kutilgan parametrlarni olmasa
             print(f"Report service function call error: {e}")
             print(f"Service: {self.data_service.__name__}, Params: {params}")
             return Response({"error": f"Hisobot xizmatini chaqirishda xatolik (parametrlar mos kelmadi): {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            # Servis funksiyasi ichidagi boshqa xatoliklar
            print(f"Error generating report ({self.data_service.__name__}): {e}") # Loglash muhim
            # Xatolik haqida umumiy xabar berish
            return Response({"error": "Hisobot yaratishda ichki xatolik yuz berdi."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def extract_extra_params(self, request, params):
        """
        Har bir hisobot uchun o'ziga xos qo'shimcha parametrlarni
        request.query_params dan olib, params dictiga qo'shadi.
        Subklasslarda override qilinishi kerak.
        Misol: params['seller_id'] = request.query_params.get('seller_id')
        """
        pass # Default implementatsiya hech narsa qilmaydi



class SalesReportView(BaseReportView):
    """Sotuvlar hisoboti uchun API view"""
    optional_params = BaseReportView.optional_params + ['seller_id', 'kassa_id', 'payment_type', 'group_by']
    data_service = get_sales_report_data

    def extract_extra_params(self, request, params):
        params['seller_id'] = request.query_params.get('seller_id')
        params['kassa_id'] = request.query_params.get('kassa_id')
        params['payment_type'] = request.query_params.get('payment_type')
        params['group_by'] = request.query_params.get('group_by')


class ProductsReportView(BaseReportView):
    """Mahsulotlar hisoboti uchun API view"""
    optional_params = BaseReportView.optional_params + ['category_id']
    data_service = get_products_report_data

    def extract_extra_params(self, request, params):
        params['category_id'] = request.query_params.get('category_id')


class SellersReportView(BaseReportView):
    """Sotuvchilar hisoboti uchun API view"""
    # Qo'shimcha parametrlar hozircha yo'q
    data_service = get_sellers_report_data


class InstallmentsReportView(BaseReportView):
     """Nasiyalar hisoboti uchun API view"""
     required_params = [] # Sanalar ixtiyoriy
     optional_params = ['start_date', 'end_date', 'customer_id', 'status'] # currency kerak emas
     data_service = get_installments_report_data

     def get(self, request): # BaseReportView.get ni override qilish (valyuta tekshirish shart emas)
         params = {}
         # Sanalar (ixtiyoriy)
         start_date_str = request.query_params.get('start_date')
         end_date_str = request.query_params.get('end_date')
         try:
             params['start_date'] = parse_date(start_date_str) if start_date_str else None
             params['end_date'] = parse_date(end_date_str) if end_date_str else None
             if params['start_date'] and params['end_date'] and params['start_date'] > params['end_date']:
                  raise ValueError("Boshlanish sanasi tugash sanasidan keyin.")
         except (ValueError, TypeError) as e:
              return Response({"error": f"Sana parametrlarida xatolik: {e}. YYYY-MM-DD formatida kiriting."}, status=status.HTTP_400_BAD_REQUEST)

         # Boshqa parametrlarni olish
         params['customer_id'] = request.query_params.get('customer_id')
         params['status'] = request.query_params.get('status')

         # Service funksiyasini chaqirish
         if not self.data_service:
             return Response({"error": "Hisobot xizmati aniqlanmagan."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
         try:
             report_data = self.data_service(**params)
             return Response(report_data)
         except Exception as e:
              print(f"Error generating installments report: {e}")
              return Response({"error": "Nasiyalar hisobotini yaratishda xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

     def extract_extra_params(self, request, params):
         # Qiymatlarni olish
         params['customer_id'] = request.query_params.get('customer_id')
         params['status'] = request.query_params.get('status')
         # Validatsiya (masalan, status mavjud variantlardan birimi?)
         if params['status'] and params['status'] not in InstallmentPlan.PlanStatus.values:
             raise ValueError(f"Noto'g'ri status qiymati. Mumkin bo'lganlar: {InstallmentPlan.PlanStatus.labels}")