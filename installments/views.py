# installments/views.py
from rest_framework import viewsets, generics, status, filters, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import InstallmentPlan, InstallmentPayment
from .serializers import (
    InstallmentPlanListSerializer, InstallmentPlanDetailSerializer,
    InstallmentPaySerializer, InstallmentPaymentSerializer
)

class InstallmentPlanViewSet(viewsets.ReadOnlyModelViewSet): # Faqat o'qish va maxsus 'pay' action
    """Nasiya rejalarini ko'rish va to'lov qilish"""
    permission_classes = [permissions.IsAuthenticated] # Kimlar ko'ra oladi? (Admin, Menejer, Sotuvchi?)
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    # Filtrlash maydonlari
    filterset_fields = {
        'created_at': ['date', 'date__gte', 'date__lte'],
        'next_payment_date': ['date', 'date__gte', 'date__lte', 'isnull'],
        'customer': ['exact'],
        'status': ['exact', 'in'],
        'sale__kassa': ['exact'], # Qaysi kassadagi sotuvlar
    }
    search_fields = ['id', 'sale__id', 'customer__full_name', 'customer__phone_number']
    ordering_fields = ['created_at', 'next_payment_date', 'status', 'remaining_amount']

    def get_serializer_class(self):
        if self.action == 'list':
            return InstallmentPlanListSerializer
        # retrieve, pay actionlari uchun Detail serializer
        return InstallmentPlanDetailSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = InstallmentPlan.objects.select_related(
            'sale__seller', 'customer', 'sale__kassa', 'store' # store qo'shildi
        ).prefetch_related(
            'payments__received_by'
        ) # .all() olib tashlandi

        if user.is_superuser:
            store_id = self.request.query_params.get('store_id')
            if store_id:
                queryset = queryset.filter(store_id=store_id)
            # Hamma nasiyalarni qaytarish
        elif hasattr(user, 'profile') and user.profile.store:
            queryset = queryset.filter(store=user.profile.store)
        else:
            queryset = queryset.none()

        return queryset.order_by('-created_at') # Order by qo'shish

    @action(detail=True, methods=['post'], url_path='pay', permission_classes=[permissions.IsAuthenticated]) # Yoki IsSeller/IsAdmin
    def make_payment(self, request, pk=None):
        """Nasiyaga to'lov qilish"""
        plan = self.get_object()

        # Faqat Aktiv yoki Kechikkan rejalarga to'lov qilish mumkin
        if plan.status not in [InstallmentPlan.PlanStatus.ACTIVE, InstallmentPlan.PlanStatus.OVERDUE]:
            return Response(
                {"error": f"Ushbu nasiya rejasi '{plan.get_status_display()}' holatida. To'lov qilish mumkin emas."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = InstallmentPaySerializer(data=request.data, context={'plan': plan})
        if serializer.is_valid():
             try:
                 # Serializer.save() to'lovni qaytaradi
                 payment_data = serializer.save(plan=plan, user=request.user)
                 # Yangilangan plan ma'lumotini qaytarish
                 updated_plan_serializer = self.get_serializer(plan) # Detail serializer ishlatiladi
                 response_data = updated_plan_serializer.data
                 response_data['last_payment'] = payment_data # Oxirgi to'lovni ham qo'shish
                 return Response(response_data, status=status.HTTP_200_OK)
             except serializers.ValidationError as e:
                  return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
             except Exception as e:
                  print(f"Error making installment payment for plan {pk}: {e}") # Loglash
                  return Response({"error": "To'lovni amalga oshirishda xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)