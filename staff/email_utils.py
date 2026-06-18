from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

def send_shift_notification(shift, action='created'):
    employee = shift.employee
    if not employee.email:
        return False
    
    subject_map = {
        'created': f'🏨 Νέα Βάρδια - {shift.date.strftime("%d/%m/%Y")}',
        'updated': f'📝 Ενημέρωση Βάρδιας - {shift.date.strftime("%d/%m/%Y")}',
        'cancelled': f'❌ Ακύρωση Βάρδιας - {shift.date.strftime("%d/%m/%Y")}',
        'reminder': f'⏰ Υπενθύμιση Βάρδιας - Αύριο {shift.date.strftime("%d/%m/%Y")}',
    }
    
    context = {
        'employee': employee,
        'shift': shift,
        'department': shift.department,
        'hotel': shift.department.hotel,
        'action': action,
    }
    
    html_content = render_to_string('staff/emails/shift_notification.html', context)
    text_content = f"Γεια σου {employee.first_name}, Βάρδια: {shift.date.strftime('%d/%m/%Y')} {shift.start_time.strftime('%H:%M')}-{shift.end_time.strftime('%H:%M')}"
    
    msg = EmailMultiAlternatives(
        subject=subject_map.get(action, 'Hotel Staff - Βάρδια'),
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[employee.email],
    )
    msg.attach_alternative(html_content, "text/html")
    
    if shift.department.manager and shift.department.manager.email:
        msg.cc = [shift.department.manager.email]
    
    try:
        msg.send()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def send_daily_summary(department, date=None):
    from django.utils import timezone
    if not date:
        date = timezone.now().date()
    
    shifts = department.shifts.filter(date=date).select_related('employee')
    if not shifts.exists():
        return False
    
    total_hours = sum(s.scheduled_hours for s in shifts)
    total_wages = sum(s.daily_wage for s in shifts if s.status == 'completed')
    
    context = {
        'department': department,
        'hotel': department.hotel,
        'date': date,
        'shifts': shifts,
        'total_hours': total_hours,
        'total_wages': total_wages,
        'shift_count': shifts.count(),
    }
    
    html_content = render_to_string('staff/emails/daily_summary.html', context)
    
    msg = EmailMultiAlternatives(
        subject=f'📊 Daily Summary - {department.name} - {date.strftime("%d/%m/%Y")}',
        body=f'Summary for {department.name}',
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[department.manager.email] if department.manager else [],
    )
    msg.attach_alternative(html_content, "text/html")
    
    try:
        msg.send()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False