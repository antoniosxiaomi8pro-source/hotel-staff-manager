from django.contrib import admin
from .admin_forms import EmployeeAdminForm
from .models import Hotel, Department, Employee, EmployeeDepartment, Shift, OvertimeRule, ShiftOvertime, ShiftTemplate, GlobalShiftTemplate

@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ["name", "address"]
    search_fields = ["name"]

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "hotel", "manager"]
    list_filter = ["hotel"]
    search_fields = ["name"]

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["full_name", "salary_type", "contract_type", "is_active"]
    list_filter = ["contract_type", "salary_type", "is_active"]
    search_fields = ["first_name", "last_name", "email"]
    list_editable = ["is_active"]

@admin.register(EmployeeDepartment)
class EmployeeDepartmentAdmin(admin.ModelAdmin):
    list_display = ["employee", "department", "hours_per_day", "is_primary", "is_active_now"]
    list_filter = ["department__hotel", "department", "is_primary"]
    search_fields = ["employee__first_name", "employee__last_name"]

@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ["employee", "department", "date", "shift_type", "start_time", "end_time", "status", "daily_wage"]
    list_filter = ["department__hotel", "department", "status", "date"]
    date_hierarchy = "date"
    search_fields = ["employee__first_name", "employee__last_name"]
    list_editable = ["status"]

@admin.register(OvertimeRule)
class OvertimeRuleAdmin(admin.ModelAdmin):
    list_display = ["hotel", "name", "multiplier", "days_of_week", "is_holiday"]
    list_filter = ["hotel"]

@admin.register(ShiftOvertime)
class ShiftOvertimeAdmin(admin.ModelAdmin):
    list_display = ["shift", "rule", "hours", "amount"]

@admin.register(ShiftTemplate)
class ShiftTemplateAdmin(admin.ModelAdmin):
    list_display = ["department", "name", "start_time", "end_time", "is_active"]
    list_filter = ["department__hotel", "department"]
    search_fields = ["name"]
    list_editable = ["is_active"]

@admin.register(GlobalShiftTemplate)
class GlobalShiftTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_time', 'end_time', 'is_active']
    list_editable = ['is_active']
    search_fields = ['name']
