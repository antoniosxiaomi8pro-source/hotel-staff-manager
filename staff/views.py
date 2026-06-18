from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from datetime import datetime, timedelta
import calendar

from .models import Hotel, Department, Employee, EmployeeDepartment, Shift, ShiftTemplate, ShiftOvertime, DailyHotelStats
from .decorators import manager_required, hr_or_manager_required, hr_required
from .email_utils import send_shift_notification, send_daily_summary
from .excel_export import export_payroll_excel, export_employee_list
from .overtime_utils import calculate_overtime

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Λάθος στοιχεία σύνδεσης')
    return render(request, 'staff/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    user = request.user
    is_hr = user.groups.filter(name='HR').exists() or user.is_staff or user.is_superuser
    is_manager = Department.objects.filter(manager=user).exists()
    
    context = {'is_hr': is_hr, 'is_manager': is_manager}
    
    if is_hr:
        today = timezone.now().date()
        month_start = today.replace(day=1)
        shifts = Shift.objects.filter(date__range=[month_start, today], status='completed')
        context['total_employees'] = Employee.objects.filter(is_active=True).count()
        context['total_shifts_today'] = Shift.objects.filter(date=today).count()
        context['monthly_wages'] = round(sum(s.daily_wage for s in shifts), 2)
        context['hotels'] = Hotel.objects.all()
    
    # ΓΙΑ HR/SUPER ADMIN: ΌΛΑ τα τμήματα
    if is_hr:
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        dept_shifts = []
        for dept in Department.objects.all():  # ← ΌΛΑ τα τμήματα!
            shifts = Shift.objects.filter(department=dept, date__range=[week_start, week_end]).select_related('employee').order_by('date', 'start_time')
            shifts_by_day = {week_start + timedelta(days=i): [] for i in range(7)}
            for s in shifts:
                shifts_by_day[s.date].append(s)
            dept_shifts.append({
                'department': dept,
                'shifts_by_day': shifts_by_day,
                'employee_count': EmployeeDepartment.objects.filter(department=dept, end_date__isnull=True).count()
            })
        context['dept_shifts'] = dept_shifts
        context['week_range'] = f"{week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m/%Y')}"
    
    # ΓΙΑ MANAGER (όχι HR): Μόνο τα δικά του τμήματα
    elif is_manager:
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        managed_depts = Department.objects.filter(manager=user)
        dept_shifts = []
        for dept in managed_depts:
            shifts = Shift.objects.filter(department=dept, date__range=[week_start, week_end]).select_related('employee').order_by('date', 'start_time')
            shifts_by_day = {week_start + timedelta(days=i): [] for i in range(7)}
            for s in shifts:
                shifts_by_day[s.date].append(s)
            dept_shifts.append({
                'department': dept,
                'shifts_by_day': shifts_by_day,
                'employee_count': EmployeeDepartment.objects.filter(department=dept, end_date__isnull=True).count()
            })
        context['dept_shifts'] = dept_shifts
        context['week_range'] = f"{week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m/%Y')}"
    
    # ΓΙΑ ΥΠΑΛΛΗΛΟ: Στατιστικά
    else:
        try:
            employee = request.user.employee
            today = timezone.now().date()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            month_start = today.replace(day=1)
            year_start = today.replace(month=1, day=1)
            
            # Σημερινές βάρδιες
            today_shifts = Shift.objects.filter(employee=employee, date=today)
            context['today_shifts'] = today_shifts
            context['today_hours'] = round(sum(s.scheduled_hours for s in today_shifts), 1)
            
            # Εβδομαδιαίες βάρδιες
            week_shifts = Shift.objects.filter(employee=employee, date__range=[week_start, week_end])
            context['week_shifts_count'] = week_shifts.count()
            context['week_hours'] = round(sum(s.scheduled_hours for s in week_shifts), 1)
            
            # Μηνιαίες βάρδιες
            month_shifts = Shift.objects.filter(employee=employee, date__range=[month_start, today])
            context['month_shifts_count'] = month_shifts.count()
            context['month_hours'] = round(sum(s.scheduled_hours for s in month_shifts), 1)
            
            # Ετήσιες βάρδιες
            year_shifts = Shift.objects.filter(employee=employee, date__range=[year_start, today])
            context['year_shifts_count'] = year_shifts.count()
            context['year_hours'] = round(sum(s.scheduled_hours for s in year_shifts), 1)
            
            context['employee'] = employee
        except Employee.DoesNotExist:
            pass
    
    return render(request, 'staff/dashboard.html', context)

@manager_required
def department_staff(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)
    emp_depts = EmployeeDepartment.objects.filter(department=department, end_date__isnull=True).select_related('employee')
    return render(request, 'staff/department_staff.html', {'department': department, 'emp_depts': emp_depts})

@manager_required
def shift_schedule(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)
    
    date_str = request.GET.get('date')
    if date_str:
        current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        current_date = timezone.now().date()
    
    week_start = current_date - timedelta(days=current_date.weekday())
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    
    shifts = Shift.objects.filter(department=department, date__range=[week_start, week_start + timedelta(days=6)]).select_related('employee').order_by('date', 'start_time')
    
    shifts_by_day = {d: [] for d in week_dates}
    for shift in shifts:
        shifts_by_day[shift.date].append(shift)
    
    prev_week = (week_start - timedelta(days=7)).strftime('%Y-%m-%d')
    next_week = (week_start + timedelta(days=7)).strftime('%Y-%m-%d')
    
    available_employees = EmployeeDepartment.objects.filter(
        department=department, 
        end_date__isnull=True
    ).select_related('employee').order_by('employee__last_name')
    
    # Φέρε τα active templates για αυτό το τμήμα
    shift_templates = department.shift_templates.filter(is_active=True)
    
    return render(request, 'staff/shift_schedule.html', {
        'department': department, 'week_dates': week_dates, 'shifts_by_day': shifts_by_day,
        'current_week': week_start, 'prev_week': prev_week, 'next_week': next_week,
        'available_employees': available_employees, 'today': timezone.now().date(),
        'shift_templates': shift_templates
    })

@manager_required
def add_shift(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)
    
    if request.method == 'POST':
        employee_id = request.POST.get('employee')
        date = request.POST.get('date')
        shift_type = request.POST.get('shift_type')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        notes = request.POST.get('notes', '')
        
        if shift_type != 'custom':
            times = {'morning': ('07:00', '15:00'), 'afternoon': ('15:00', '23:00'), 'night': ('23:00', '07:00')}
            if shift_type in times:
                start_time, end_time = times[shift_type]
        
        employee = get_object_or_404(Employee, id=employee_id)
        
        emp_dept = EmployeeDepartment.objects.filter(employee=employee, department=department, end_date__isnull=True).first()
        
        shift = Shift.objects.create(
            employee=employee, department=department, employee_department=emp_dept,
            date=date, shift_type=shift_type, start_time=start_time, end_time=end_time,
            notes=notes, created_by=request.user, status='scheduled'
        )
        
        calculate_overtime(shift)
        send_shift_notification(shift, action='created')
        
        messages.success(request, f'Η βάρδια προστέθηκε για {employee.full_name}')
        return redirect('shift_schedule', dept_id=dept_id)
    
    return redirect('shift_schedule', dept_id=dept_id)

@manager_required
def edit_shift(request, shift_id):
    shift = get_object_or_404(Shift, id=shift_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update':
            from datetime import datetime
            start_time_str = request.POST.get('start_time')
            end_time_str = request.POST.get('end_time')
            if start_time_str:
                shift.start_time = datetime.strptime(start_time_str, '%H:%M').time()
            if end_time_str:
                shift.end_time = datetime.strptime(end_time_str, '%H:%M').time()
            shift.status = request.POST.get('status')
            shift.notes = request.POST.get('notes', '')
            shift.save()
            shift.overtimes.all().delete()
            calculate_overtime(shift)
            send_shift_notification(shift, action='updated')
            messages.success(request, 'Η βάρδια ενημερώθηκε')
            
        elif action == 'complete':
            shift.actual_start = request.POST.get('actual_start')
            shift.actual_end = request.POST.get('actual_end')
            shift.status = 'completed'
            shift.save()
            shift.overtimes.all().delete()
            calculate_overtime(shift)
            messages.success(request, f'Βάρδια ολοκληρώθηκε. Ημερομίσθιο: €{shift.daily_wage}')
            
        elif action == 'cancel':
            shift.status = 'cancelled'
            shift.save()
            send_shift_notification(shift, action='cancelled')
            messages.success(request, 'Η βάρδια ακυρώθηκε')
            
        elif action == 'delete':
            send_shift_notification(shift, action='cancelled')
            shift.delete()
            messages.success(request, 'Η βάρδια διαγράφηκε')
        
        return redirect('shift_schedule', dept_id=shift.department.id)
    
    return render(request, 'staff/edit_shift.html', {'shift': shift})

@hr_required
def hr_employees(request):
    employees = Employee.objects.filter(is_active=True)
    hotel_id = request.GET.get('hotel')
    if hotel_id:
        emp_ids = EmployeeDepartment.objects.filter(department__hotel_id=hotel_id, end_date__isnull=True).values_list('employee_id', flat=True)
        employees = employees.filter(id__in=emp_ids)
    return render(request, 'staff/hr_employees.html', {'employees': employees, 'hotels': Hotel.objects.all()})

@hr_required
def hr_wages(request):
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    month_start = datetime(year, month, 1).date()
    if month == 12:
        month_end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        month_end = datetime(year, month + 1, 1).date() - timedelta(days=1)
    
    hotels_data = []
    for hotel in Hotel.objects.all():
        hotel_shifts = Shift.objects.filter(department__hotel=hotel, date__range=[month_start, month_end], status='completed')
        total_wages = sum(s.daily_wage for s in hotel_shifts)
        total_hours = sum(s.actual_hours or s.scheduled_hours for s in hotel_shifts)
        hotels_data.append({
            'hotel': hotel, 'total_wages': round(total_wages, 2), 'total_hours': round(total_hours, 2),
            'shift_count': hotel_shifts.count(),
            'employee_count': EmployeeDepartment.objects.filter(department__hotel=hotel, end_date__isnull=True).values('employee').distinct().count()
        })
    
    shifts = Shift.objects.filter(date__range=[month_start, month_end], status__in=['completed', 'scheduled']).select_related('employee', 'department').order_by('date')
    
    return render(request, 'staff/hr_wages.html', {
        'month_name': calendar.month_name[month], 'year': year, 'month': month,
        'hotels_data': hotels_data, 'shifts': shifts,
        'total_monthly_wages': sum(h['total_wages'] for h in hotels_data),
        'prev_month': f"{year}-{month-1:02d}" if month > 1 else f"{year-1}-12",
        'next_month': f"{year}-{month+1:02d}" if month < 12 else f"{year+1}-01"
    })

@hr_required
def employee_detail(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    three_months_ago = timezone.now().date() - timedelta(days=90)
    shifts = Shift.objects.filter(employee=employee, date__gte=three_months_ago).order_by('-date')
    
    emp_depts = EmployeeDepartment.objects.filter(employee=employee).select_related('department').order_by('-is_primary', '-start_date')
    
    monthly_stats = []
    for i in range(3):
        month_date = timezone.now().date() - timedelta(days=30*i)
        month_shifts = shifts.filter(date__year=month_date.year, date__month=month_date.month, status='completed')
        total_wage = sum(s.daily_wage for s in month_shifts)
        total_hours = sum(s.actual_hours or s.scheduled_hours for s in month_shifts)
        monthly_stats.append({
            'month': month_date.strftime('%B %Y'), 'shifts': month_shifts.count(),
            'hours': round(total_hours, 2), 'wage': round(total_wage, 2),
        })
    
    return render(request, 'staff/employee_detail.html', {
        'employee': employee, 'shifts': shifts[:30], 'monthly_stats': monthly_stats, 'emp_depts': emp_depts
    })

@hr_required
def export_payroll(request):
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    month_start = datetime(year, month, 1).date()
    if month == 12:
        month_end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        month_end = datetime(year, month + 1, 1).date() - timedelta(days=1)
    
    hotel_id = request.GET.get('hotel')
    shifts = Shift.objects.filter(date__range=[month_start, month_end], status='completed').select_related('employee', 'department', 'department__hotel')
    if hotel_id:
        shifts = shifts.filter(department__hotel_id=hotel_id)
    
    return export_payroll_excel(shifts, f"payroll_{month:02d}_{year}")

@hr_required
def export_employees(request):
    employees = Employee.objects.filter(is_active=True).select_related()
    hotel_id = request.GET.get('hotel')
    if hotel_id:
        emp_ids = EmployeeDepartment.objects.filter(department__hotel_id=hotel_id, end_date__isnull=True).values_list('employee_id', flat=True)
        employees = employees.filter(id__in=emp_ids)
    return export_employee_list(employees)

@manager_required
def add_employee_to_dept(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        role = request.POST.get('role')
        contract_type = request.POST.get('contract_type', 'full_time')
        salary_type = request.POST.get('salary_type', 'none')
        hourly_wage = request.POST.get('hourly_wage') or None
        monthly_salary = request.POST.get('monthly_salary') or None
        daily_wage_fixed = request.POST.get('daily_wage_fixed') or None
        hours_per_day = request.POST.get('hours_per_day', 8.00)
        
        employee = Employee.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            role=role,
            contract_type=contract_type,
            salary_type=salary_type,
            hourly_wage=hourly_wage,
            monthly_salary=monthly_salary,
            daily_wage_fixed=daily_wage_fixed,
            is_active=True
        )
        
        EmployeeDepartment.objects.create(
            employee=employee,
            department=department,
            hours_per_day=hours_per_day,
            is_primary=True
        )
        
        messages.success(request, f'✅ Ο {employee.full_name} προστέθηκε στο {department.name}!')
        return redirect('shift_schedule', dept_id=dept_id)
    
    return redirect('shift_schedule', dept_id=dept_id)

@manager_required
def send_daily_summary_now(request, dept_id):
    department = get_object_or_404(Department, id=dept_id)
    date_str = request.GET.get('date')
    date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.now().date()
    
    if send_daily_summary(department, date):
        messages.success(request, 'Το daily summary στάλθηκε επιτυχώς')
    else:
        messages.error(request, 'Σφάλμα αποστολής email')
    
    return redirect('shift_schedule', dept_id=dept_id)

@manager_required
def add_bulk_shifts(request, dept_id):
    """Προσθήκη πολλών βαρδιών μαζί με checkbox - Χρησιμοποιεί ShiftTemplate από admin"""
    department = get_object_or_404(Department, id=dept_id)
    
    if request.method == 'POST':
        shifts_data = request.POST.getlist('shifts')
        selected_template_id = request.POST.get('selected_template', '')
        custom_start = request.POST.get('custom_start', '07:00')
        custom_end = request.POST.get('custom_end', '15:00')
        
        created_count = 0
        errors = []
        
        # Βρες ώρες από template ή custom
        if selected_template_id and selected_template_id != 'custom':
            try:
                template = ShiftTemplate.objects.get(id=selected_template_id, department=department)
                start_time = template.start_time
                end_time = template.end_time
                shift_type = template.name.lower().replace(' ', '_')
            except ShiftTemplate.DoesNotExist:
                messages.error(request, '❌ Template δεν βρέθηκε!')
                return redirect('shift_schedule', dept_id=dept_id)
        else:
            start_time = custom_start
            end_time = custom_end
            shift_type = 'custom'
        
        for shift_data in shifts_data:
            # Format: "YYYY-MM-DD|employee_id"
            parts = shift_data.split('|')
            if len(parts) != 2:
                continue
                
            date_str, employee_id = parts
            
            try:
                employee = Employee.objects.get(id=employee_id)
                emp_dept = EmployeeDepartment.objects.filter(
                    employee=employee, 
                    department=department, 
                    end_date__isnull=True
                ).first()
                
                # Έλεγχος αν υπάρχει ήδη βάρδια την ίδια μέρα
                existing = Shift.objects.filter(
                    employee=employee,
                    department=department,
                    date=date_str,
                    start_time=start_time
                ).exists()
                
                if existing:
                    errors.append(f"⚠️ {employee.full_name} έχει ήδη βάρδια {date_str}")
                    continue
                
                shift = Shift.objects.create(
                    employee=employee,
                    department=department,
                    employee_department=emp_dept,
                    date=date_str,
                    shift_type=shift_type,
                    start_time=start_time,
                    end_time=end_time,
                    created_by=request.user,
                    status='scheduled'
                )
                
                calculate_overtime(shift)
                created_count += 1
                
            except Employee.DoesNotExist:
                errors.append(f"❌ Υπάλληλος {employee_id} δεν βρέθηκε")
        
        # Μηνύματα
        if created_count > 0:
            messages.success(request, f'✅ Δημιουργήθηκαν {created_count} βάρδιες!')
        
        if errors:
            for error in errors[:5]:
                messages.warning(request, error)
        
        return redirect('shift_schedule', dept_id=dept_id)
    
    return redirect('shift_schedule', dept_id=dept_id)

# ========== ADMIN IMPORT VIEW ==========
import pandas as pd
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def import_employees_view(request):
    """Import υπαλλήλων από Excel/CSV - Admin UI"""
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

@manager_required
def add_employee_to_multiple_depts(request):
    """Προσθήκη υπαλλήλου σε πολλά τμήματα από το UI"""
    
    # Έλεγχος αν ο χρήστης είναι HR (βλέπει όλα) ή Manager (βλέπει μόνα του)
    is_hr = request.user.groups.filter(name="HR").exists() or request.user.is_superuser or request.user.is_staff
    
    if request.method == 'POST':
        employee_id = request.POST.get('employee')
        department_ids = request.POST.getlist('departments')
        hours_per_day = request.POST.get('hours_per_day', 8.0)
        
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            messages.error(request, '❌ Υπάλληλος δεν βρέθηκε!')
            return redirect('dashboard')
        
        # 🔒 SECURITY: Manager μπορεί να προσθέσει ΜΟΝΟ στα δικά του τμήματα
        if not is_hr:
            manager_dept_ids = set(
                Department.objects.filter(manager=request.user)
                .values_list('id', flat=True)
            )
            selected_ids = set(int(d) for d in department_ids if d)
            unauthorized = selected_ids - manager_dept_ids
            
            if unauthorized:
                messages.error(
                    request, 
                    f'❌ Δεν έχεις δικαίωμα να προσθέσεις υπαλλήλους σε {len(unauthorized)} τμήματα που δεν διαχειρίζεσαι!'
                )
                return redirect('add_employee_to_multiple_depts')
        
        added = 0
        for dept_id in department_ids:
            try:
                dept = Department.objects.get(id=dept_id)
                EmployeeDepartment.objects.get_or_create(
                    employee=employee,
                    department=dept,
                    defaults={
                        'hours_per_day': hours_per_day,
                        'is_primary': False
                    }
                )
                added += 1
            except Department.DoesNotExist:
                pass
        
        messages.success(request, f'✅ Ο {employee.full_name} προστέθηκε σε {added} τμήματα!')
        return redirect('dashboard')
    
    # GET - Φιλτράρισμα τμημάτων ανάλογα με τον χρήστη
    if is_hr:
        # HR βλέπει όλα τα τμήματα
        departments = Department.objects.all().select_related('hotel')
    else:
        # Manager βλέπει ΜΟΝΟ τα δικά του τμήματα
        departments = Department.objects.filter(
            manager=request.user
        ).select_related('hotel')
    
    employees = Employee.objects.filter(is_active=True)
    
    return render(request, 'staff/add_employee_multi_dept.html', {
        'employees': employees,
        'departments': departments,
        'is_hr': is_hr,  # Περνάμε στο template για να ξέρει τι να δείξει
    })



@hr_required
def daily_hr_report(request):
    """Daily HR Report - Τι παραλαμβάνει το HR κάθε μέρα"""
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    
    # Όλες οι βάρδιες της ημέρας
    today_shifts = Shift.objects.filter(date=today).select_related('employee', 'department', 'department__hotel').order_by('department__name', 'start_time')
    
    # Ομαδοποίηση ανά τμήμα
    dept_data = {}
    for shift in today_shifts:
        dept_name = f"{shift.department.hotel.name} - {shift.department.name}"
        if dept_name not in dept_data:
            dept_data[dept_name] = {
                'shifts': [],
                'total_wages': 0,
                'total_overtime': 0,
                'present': 0,
                'absent': 0,
                'scheduled': 0
            }
        dept_data[dept_name]['shifts'].append(shift)
        dept_data[dept_name]['total_wages'] += shift.daily_wage or 0
        
        # Υπολογισμός παρουσιών/απουσιών
        if shift.status == 'completed':
            dept_data[dept_name]['present'] += 1
        elif shift.status == 'absent':
            dept_data[dept_name]['absent'] += 1
        elif shift.status == 'scheduled':
            dept_data[dept_name]['scheduled'] += 1
    
    # Υπερωρίες της ημέρας
    today_overtimes = ShiftOvertime.objects.filter(shift__date=today).select_related('shift', 'shift__employee', 'rule')
    
    # Συνολικά στατιστικά
    total_wages = sum(d['total_wages'] for d in dept_data.values())
    total_overtime_cost = sum(ot.cost for ot in today_overtimes)
    total_present = sum(d['present'] for d in dept_data.values())
    total_absent = sum(d['absent'] for d in dept_data.values())
    total_scheduled = sum(d['scheduled'] for d in dept_data.values())
    
    context = {
        'today': today,
        'dept_data': dept_data,
        'today_overtimes': today_overtimes,
        'total_wages': round(total_wages, 2),
        'total_overtime_cost': round(total_overtime_cost, 2),
        'total_present': total_present,
        'total_absent': total_absent,
        'total_scheduled': total_scheduled,
        'total_employees': Employee.objects.filter(is_active=True).count(),
    }
    
    return render(request, 'staff/daily_hr_report.html', context)


@manager_required
def attendance_confirmation(request, dept_id):
    """Επιβεβαίωση παρουσιών/απουσιών από τον manager"""
    department = get_object_or_404(Department, id=dept_id)
    
    # Έλεγχος αν ο user είναι manager του τμήματος
    if request.user != department.manager and not request.user.groups.filter(name='HR').exists():
        messages.error(request, '❌ Δεν έχετε δικαίωμα πρόσβασης σε αυτό το τμήμα!')
        return redirect('dashboard')
    
    today = timezone.now().date()
    
    if request.method == 'POST':
        # Ενημέρωση status για κάθε βάρδια
        for key, value in request.POST.items():
            if key.startswith('shift_'):
                shift_id = key.replace('shift_', '')
                try:
                    shift = Shift.objects.get(id=shift_id, department=department)
                    if value in ['completed', 'absent']:
                        shift.status = value
                        shift.save()
                except Shift.DoesNotExist:
                    pass
        messages.success(request, '✅ Οι παρουσίες/απουσίες ενημερώθηκαν επιτυχώς!')
        return redirect('attendance_confirmation', dept_id=dept_id)
    
    # GET - Εμφάνιση βαρδιών σήμερα
    today_shifts = Shift.objects.filter(
        department=department, 
        date=today
    ).select_related('employee').order_by('start_time')
    
    return render(request, 'staff/attendance_confirmation.html', {
        'department': department,
        'today': today,
        'shifts': today_shifts,
    })


@login_required
def my_schedule(request):
    """Ο υπάλληλος βλέπει το δικό του πρόγραμμα βαρδιών"""
    try:
        employee = request.user.employee
    except Employee.DoesNotExist:
        messages.error(request, '❌ Δεν έχετε συνδεδεμένο προφίλ υπαλλήλου!')
        return redirect('dashboard')
    
    # Εβδομάδα: από Δευτέρα έως Κυριακή
    today = timezone.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    
    # Όλες οι βάρδιες της εβδομάδας
    shifts = Shift.objects.filter(
        employee=employee,
        date__range=[monday, sunday]
    ).select_related('department', 'department__hotel').order_by('date', 'start_time')
    
    # Ομαδοποίηση ανά ημέρα
    shifts_by_day = {}
    for i in range(7):
        day = monday + timedelta(days=i)
        shifts_by_day[day] = []
    
    for shift in shifts:
        shifts_by_day[shift.date].append(shift)
    
    # Στατιστικά εβδομάδας
    total_shifts = shifts.count()
    total_hours = sum(shift.scheduled_hours for shift in shifts)
    
    context = {
        'employee': employee,
        'shifts_by_day': shifts_by_day,
        'monday': monday,
        'sunday': sunday,
        'total_shifts': total_shifts,
        'total_hours': round(total_hours, 1),
    }
    
    return render(request, 'staff/my_schedule.html', context)


# ============================================
# EXECUTIVE DASHBOARD & DAILY STATS
# ============================================

from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from django.db.models import Sum, Avg, Count, F

@hr_required
def daily_stats_entry(request):
    """Καταχώρηση ημερήσιων στατιστικών ξενοδοχείου"""
    default_date = (timezone.now() - timedelta(days=1)).date()
    hotels = Hotel.objects.all()
    
    if request.method == 'POST':
        hotel_id = request.POST.get('hotel')
        date_str = request.POST.get('date')
        
        try:
            hotel = Hotel.objects.get(id=hotel_id)
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            stats, created = DailyHotelStats.objects.get_or_create(
                hotel=hotel,
                date=date,
                defaults={'entered_by': request.user}
            )
            
            stats.total_rooms = int(request.POST.get('total_rooms', 0))
            stats.occupied_rooms = int(request.POST.get('occupied_rooms', 0))
            stats.check_ins = int(request.POST.get('check_ins', 0))
            stats.check_outs = int(request.POST.get('check_outs', 0))
            stats.room_revenue = Decimal(request.POST.get('room_revenue', 0))
            stats.fb_revenue = Decimal(request.POST.get('fb_revenue', 0))
            stats.extras_revenue = Decimal(request.POST.get('extras_revenue', 0))
            
            # Auto-calculate from Staff Manager
            dept_ids = Department.objects.filter(hotel=hotel).values_list('id', flat=True)
            shifts = Shift.objects.filter(
                department_id__in=dept_ids,
                date=date
            ).select_related('employee_department')
            
            stats.staff_count = shifts.values('employee_department__employee').distinct().count()
            stats.total_wages = sum(
                s.employee_department.daily_wage for s in shifts 
                if hasattr(s, 'employee_department') and s.employee_department
            )
            
            stats.save()
            
            action = "δημιουργήθηκαν" if created else "ενημερώθηκαν"
            messages.success(
                request, 
                f'✅ Στατιστικά {hotel.name} για {date.strftime("%d/%m/%Y")} {action}!'
            )
            return redirect('daily_stats_entry')
            
        except Exception as e:
            messages.error(request, f'❌ Σφάλμα: {e}')
    
    recent_stats = DailyHotelStats.objects.filter(
        date__gte=default_date - timedelta(days=6)
    ).select_related('hotel').order_by('-date', 'hotel__name')
    
    return render(request, 'staff/daily_stats_entry.html', {
        'hotels': hotels,
        'default_date': default_date,
        'recent_stats': recent_stats,
    })


@hr_required
def edit_daily_stats(request, stats_id):
    """Επεξεργασία στατιστικών"""
    stats = get_object_or_404(DailyHotelStats, id=stats_id)
    
    if request.method == 'POST':
        stats.total_rooms = int(request.POST.get('total_rooms', 0))
        stats.occupied_rooms = int(request.POST.get('occupied_rooms', 0))
        stats.check_ins = int(request.POST.get('check_ins', 0))
        stats.check_outs = int(request.POST.get('check_outs', 0))
        stats.room_revenue = Decimal(request.POST.get('room_revenue', 0))
        stats.fb_revenue = Decimal(request.POST.get('fb_revenue', 0))
        stats.extras_revenue = Decimal(request.POST.get('extras_revenue', 0))
        stats.save()
        
        messages.success(request, f'✅ Ενημερώθηκαν για {stats.date.strftime("%d/%m/%Y")}')
        return redirect('daily_stats_entry')
    
    return render(request, 'staff/edit_daily_stats.html', {'stats': stats})


@hr_required
def executive_dashboard(request):
    """Super Admin Dashboard - Πλήρης εικόνα ομίλου"""
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    
    def get_period_stats(start_date, end_date=None):
        end_date = end_date or today
        stats = DailyHotelStats.objects.filter(date__gte=start_date, date__lte=end_date)
        total_rev = (stats.aggregate(Sum('room_revenue'))['room_revenue__sum'] or 0) + \
                    (stats.aggregate(Sum('fb_revenue'))['fb_revenue__sum'] or 0) + \
                    (stats.aggregate(Sum('extras_revenue'))['extras_revenue__sum'] or 0)
        wages = stats.aggregate(Sum('total_wages'))['total_wages__sum'] or 0
        return {
            'total_room_rev': stats.aggregate(Sum('room_revenue'))['room_revenue__sum'] or 0,
            'total_fb_rev': stats.aggregate(Sum('fb_revenue'))['fb_revenue__sum'] or 0,
            'total_extras': stats.aggregate(Sum('extras_revenue'))['extras_revenue__sum'] or 0,
            'total_wages': wages,
            'total_rev': total_rev,
            'labor_ratio': round((wages / total_rev * 100), 1) if total_rev else 0,
        }
    
    periods = {
        'yesterday': get_period_stats(yesterday, yesterday),
        'week': get_period_stats(week_start),
        'month': get_period_stats(month_start),
    }
    
    hotels = Hotel.objects.all()
    hotel_data = []
    for hotel in hotels:
        hotel_stats = DailyHotelStats.objects.filter(
            hotel=hotel, date__gte=month_start
        ).aggregate(
            room_rev=Sum('room_revenue'),
            fb_rev=Sum('fb_revenue'),
            extras=Sum('extras_revenue'),
            wages=Sum('total_wages'),
            total_days=Count('id')
        )
        
        total_rev = (hotel_stats['room_rev'] or 0) + (hotel_stats['fb_rev'] or 0) + (hotel_stats['extras'] or 0)
        wages = hotel_stats['wages'] or 0
        
        hotel_data.append({
            'hotel': hotel,
            'room_rev': hotel_stats['room_rev'] or 0,
            'fb_rev': hotel_stats['fb_rev'] or 0,
            'extras': hotel_stats['extras'] or 0,
            'total_rev': total_rev,
            'wages': wages,
            'total_occupied': hotel_stats['room_rev'] or 0,  # placeholder
            'total_checkins': hotel_stats['fb_rev'] or 0,  # placeholder,
            'labor_ratio': round((wages / total_rev * 100), 1) if total_rev else 0,
            'days_recorded': hotel_stats['total_days'],
        })
    
    daily_trend = list(DailyHotelStats.objects.filter(
        date__gte=month_start
    ).values('date').annotate(
        total_rev=Sum(F('room_revenue') + F('fb_revenue') + F('extras_revenue')),
        total_wages=Sum('total_wages'),
    
    ).order_by('date'))

    alerts = []
    for h in hotel_data:
        if h['labor_ratio'] > 25:
            alerts.append({'type': 'warning', 'hotel': h['hotel'].name, 
                          'message': f'Labor Cost {h["labor_ratio"]}% > 25%'})
        if h['days_recorded'] < (today - month_start).days:
            alerts.append({'type': 'info', 'hotel': h['hotel'].name,
                          'message': f'Λείπουν {(today - month_start).days - h["days_recorded"]} ημέρες'})
    
    return render(request, 'staff/executive_dashboard.html', {
        'periods': periods,
        'hotel_data': hotel_data,
        'daily_trend': daily_trend,
        'alerts': alerts,
        'today': today,
    })
