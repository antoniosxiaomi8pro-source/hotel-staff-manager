from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from datetime import datetime, timedelta

from .models import Hotel, Department, Employee, Shift, OvertimeRule
from .serializers import (
    HotelSerializer, DepartmentSerializer, EmployeeSerializer,
    ShiftSerializer, ShiftCreateSerializer, OvertimeRuleSerializer
)
from .overtime_utils import calculate_overtime
from .email_utils import send_shift_notification

class HotelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Hotel.objects.all()
    serializer_class = HotelSerializer
    permission_classes = [IsAuthenticated]

class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['hotel', 'manager']

class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.filter(is_active=True)
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['hotel', 'department', 'contract_type']
    search_fields = ['first_name', 'last_name', 'email']

class ShiftViewSet(viewsets.ModelViewSet):
    queryset = Shift.objects.all().select_related('employee', 'department')
    serializer_class = ShiftSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['department', 'employee', 'date', 'status', 'shift_type']
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ShiftCreateSerializer
        return ShiftSerializer
    
    def perform_create(self, serializer):
        shift = serializer.save(created_by=self.request.user, status='scheduled')
        calculate_overtime(shift)
        send_shift_notification(shift, action='created')
        return shift
    
    def perform_update(self, serializer):
        shift = serializer.save()
        shift.overtimes.all().delete()
        calculate_overtime(shift)
        send_shift_notification(shift, action='updated')
        return shift
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        shift = self.get_object()
        shift.actual_start = request.data.get('actual_start')
        shift.actual_end = request.data.get('actual_end')
        shift.status = 'completed'
        shift.save()
        shift.overtimes.all().delete()
        calculate_overtime(shift)
        return Response({'status': 'completed', 'daily_wage': shift.daily_wage, 'actual_hours': shift.actual_hours})
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        today = timezone.now().date()
        shifts = self.get_queryset().filter(date=today)
        serializer = self.get_serializer(shifts, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def week(self, request):
        date_str = request.query_params.get('date')
        if date_str:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date = timezone.now().date()
        week_start = date - timedelta(days=date.weekday())
        week_end = week_start + timedelta(days=6)
        shifts = self.get_queryset().filter(date__range=[week_start, week_end])
        serializer = self.get_serializer(shifts, many=True)
        return Response({'week_start': week_start, 'week_end': week_end, 'shifts': serializer.data})

class OvertimeRuleViewSet(viewsets.ModelViewSet):
    queryset = OvertimeRule.objects.all()
    serializer_class = OvertimeRuleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['hotel']