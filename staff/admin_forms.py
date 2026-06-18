from django import forms
from .models import Employee, Department, EmployeeDepartment

class EmployeeAdminForm(forms.ModelForm):
    """Custom form για πολλαπλή επιλογή τμημάτων"""
    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Τμήματα (πολλαπλή επιλογή)'
    )
    
    class Meta:
        model = Employee
        fields = ['first_name', 'last_name', 'email', 'phone', 'role', 'contract_type', 
                  'salary_type', 'hourly_wage', 'monthly_salary', 'daily_wage_fixed', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Προεπιλογή τμημάτων που ανήκει ήδη
            self.fields['departments'].initial = self.instance.departments.values_list('department', flat=True)
    
    def save(self, commit=True):
        employee = super().save(commit=False)
        
        if commit:
            employee.save()
        
        # Φτιάξε EmployeeDepartment για κάθε επιλεγμένο τμήμα
        if 'departments' in self.cleaned_data:
            selected_depts = self.cleaned_data['departments']
            
            # Διέγραψε τα παλιά (αν υπάρχουν)
            EmployeeDepartment.objects.filter(employee=employee).exclude(department__in=selected_depts).delete()
            
            # Φτιάξε νέα
            for dept in selected_depts:
                EmployeeDepartment.objects.get_or_create(
                    employee=employee,
                    department=dept,
                    defaults={'hours_per_day': 8.0, 'is_primary': True}
                )
        
        return employee

class EmployeeDepartmentForm(forms.ModelForm):
    """Form για το EmployeeDepartment"""
    class Meta:
        model = EmployeeDepartment
        fields = ['employee', 'department', 'start_date', 'end_date', 'hours_per_day', 'is_primary']
