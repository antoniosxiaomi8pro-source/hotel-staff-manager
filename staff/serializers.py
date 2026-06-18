from rest_framework import serializers
from .models import Hotel, Department, Employee, Shift, OvertimeRule, ShiftOvertime

class HotelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hotel
        fields = '__all__'

class DepartmentSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    manager_name = serializers.CharField(source='manager.username', read_only=True)
    
    class Meta:
        model = Department
        fields = ['id', 'name', 'hotel', 'hotel_name', 'manager', 'manager_name']

class EmployeeSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    full_name = serializers.CharField(source='full_name', read_only=True)
    
    class Meta:
        model = Employee
        fields = ['id', 'first_name', 'last_name', 'full_name', 'email', 'phone', 
                  'role', 'contract_type', 'hourly_wage', 'is_active', 
                  'hotel', 'hotel_name', 'department', 'department_name']

class ShiftOvertimeSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    multiplier = serializers.DecimalField(source='rule.multiplier', max_digits=3, decimal_places=2, read_only=True)
    
    class Meta:
        model = ShiftOvertime
        fields = ['id', 'rule', 'rule_name', 'multiplier', 'hours', 'amount']

class ShiftSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    hotel_name = serializers.CharField(source='department.hotel.name', read_only=True)
    scheduled_hours = serializers.DecimalField(max_digits=4, decimal_places=2, read_only=True)
    actual_hours = serializers.DecimalField(max_digits=4, decimal_places=2, read_only=True)
    daily_wage = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    overtimes = ShiftOvertimeSerializer(many=True, read_only=True)
    
    class Meta:
        model = Shift
        fields = ['id', 'employee', 'employee_name', 'department', 'department_name', 
                  'hotel_name', 'date', 'shift_type', 'start_time', 'end_time',
                  'status', 'notes', 'scheduled_hours', 'actual_hours', 'daily_wage',
                  'actual_start', 'actual_end', 'overtimes', 'created_at']

class ShiftCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = ['employee', 'department', 'date', 'shift_type', 'start_time', 'end_time', 'notes']

class OvertimeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = OvertimeRule
        fields = '__all__'