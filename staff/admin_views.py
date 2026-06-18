import pandas as pd
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Department, Employee, EmployeeDepartment

@staff_member_required
def import_employees_view(request):
    if request.method == 'POST':
        file = request.FILES.get('file')
        department_id = request.POST.get('department')
        
        if not file or not department_id:
            messages.error(request, '❌ Παρακαλώ επιλέξτε αρχείο και τμήμα!')
            return redirect(request.path)
        
        try:
            department = Department.objects.get(id=department_id)
        except Department.DoesNotExist:
            messages.error(request, '❌ Τμήμα δεν βρέθηκε!')
            return redirect(request.path)
        
        # Διάβασε αρχείο
        try:
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
        except Exception as e:
            messages.error(request, f'❌ Σφάλμα ανάγνωσης αρχείου: {e}')
            return redirect(request.path)
        
        # Υποχρεωτικές στήλες
        required = ['first_name', 'last_name', 'email']
        missing = [col for col in required if col not in df.columns]
        if missing:
            messages.error(request, f'❌ Λείπουν στήλες: {missing}')
            return redirect(request.path)
        
        # Import
        created = 0
        updated = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                first_name = str(row['first_name']) if pd.notna(row['first_name']) else None
                last_name = str(row['last_name']) if pd.notna(row['last_name']) else None
                email = str(row['email']) if pd.notna(row['email']) else None
                
                if not first_name or not last_name or not email:
                    errors.append(f"Σειρά {index + 2}: Λείπουν υποχρεωτικά πεδία")
                    continue
                
                emp, was_created = Employee.objects.update_or_create(
                    email=email,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'phone': str(row['phone']) if pd.notna(row.get('phone')) else '',
                        'role': str(row['role']) if pd.notna(row.get('role')) else 'Staff',
                        'contract_type': str(row['contract_type']) if pd.notna(row.get('contract_type')) else 'full_time',
                        'salary_type': str(row['salary_type']) if pd.notna(row.get('salary_type')) else 'none',
                        'hourly_wage': float(row['hourly_wage']) if pd.notna(row.get('hourly_wage')) else None,
                        'monthly_salary': float(row['monthly_salary']) if pd.notna(row.get('monthly_salary')) else None,
                        'daily_wage_fixed': float(row['daily_wage_fixed']) if pd.notna(row.get('daily_wage_fixed')) else None,
                    }
                )
                
                EmployeeDepartment.objects.get_or_create(
                    employee=emp,
                    department=department,
                    defaults={'hours_per_day': 8.0, 'is_primary': True}
                )
                
                if was_created:
                    created += 1
                else:
                    updated += 1
                    
            except Exception as e:
                errors.append(f"Σειρά {index + 2}: {e}")
        
        # Μηνύματα
        messages.success(request, f'✅ Import ολοκληρώθηκε! Δημιουργήθηκαν: {created}, Ενημερώθηκαν: {updated}')
        if errors:
            for error in errors[:5]:
                messages.warning(request, error)
        
        return redirect('/admin/staff/employee/')
    
    # GET
    departments = Department.objects.all().select_related('hotel')
    return render(request, 'staff/admin/import_employees.html', {
        'departments': departments,
        'title': 'Import Υπαλλήλων'
    })
