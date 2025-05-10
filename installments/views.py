# installments/views.py
from rest_framework import viewsets, generics, status, filters, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
# Modellarni import qilish
from .models import InstallmentPlan, InstallmentPayment
# Serializerlarni import qilish
from .serializers import (
    InstallmentPlanListSerializer, InstallmentPlanDetailSerializer,
    InstallmentPaySerializer, InstallmentPaymentSerializer
)

class InstallmentPlanViewSet(viewsets.ModelViewSet):
    """Nasiya rejalarini ko'rish va to'lov qilish"""
    # store filtri olib tashlandi
    queryset = InstallmentPlan.objects.select_related(
        'sale__seller', 'customer', 'sale__kassa'
    ).prefetch_related('payments__received_by').all().order_by('-created_at')
    permission_classes = [permissions.IsAuthenticated] # Yoki IsSeller/IsAdmin
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    # store filtri olib tashlandi
    filterset_fields = {
        'created_at': ['date', 'date__gte', 'date__lte'],
        # 'next_payment_date': ['date', 'date__gte', 'date__lte', 'isnull'],
        'customer': ['exact'],
        'status': ['exact', 'in'],
        'sale__kassa': ['exact'],
    }
    search_fields = ['id', 'sale__id', 'customer__full_name', 'customer__phone_number']
    ordering_fields = ['created_at', 'next_payment_date', 'status', 'remaining_amount']

    def get_serializer_class(self):
        if self.action == 'list':
            return InstallmentPlanListSerializer
        return InstallmentPlanDetailSerializer # retrieve, make_payment uchun

    # get_queryset soddalashtirildi
    # make_payment actioni o'zgarishsiz qoladi

    @action(detail=True, methods=['post'], url_path='pay', permission_classes=[permissions.IsAuthenticated])
    def make_payment(self, request, pk=None):
        plan = self.get_object()
        if plan.status not in [InstallmentPlan.PlanStatus.ACTIVE, InstallmentPlan.PlanStatus.OVERDUE]:
             return Response({"error": f"Ushbu nasiya rejasi '{plan.get_status_display()}' holatida. To'lov qilish mumkin emas."}, status=status.HTTP_400_BAD_REQUEST)

        # context ga request qo'shish kerak bo'lishi mumkin (agar serializer ishlatsa)
        serializer = InstallmentPaySerializer(data=request.data, context={'plan': plan, 'request': request})
        if serializer.is_valid():
             try:
                 payment_data = serializer.save(plan=plan, user=request.user)
                 updated_plan_serializer = self.get_serializer(plan)
                 response_data = updated_plan_serializer.data
                 response_data['last_payment'] = payment_data
                 return Response(response_data, status=status.HTTP_200_OK)
             except serializers.ValidationError as e:
                  return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
             except Exception as e:
                  print(f"Error making installment payment for plan {pk}: {e}")
                  return Response({"error": "To'lovni amalga oshirishda xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)