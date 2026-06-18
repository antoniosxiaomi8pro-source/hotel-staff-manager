from datetime import datetime, timedelta
from decimal import Decimal

def calculate_overtime(shift):
    from .models import OvertimeRule, ShiftOvertime
    
    overtimes = []
    rules = OvertimeRule.objects.filter(hotel=shift.department.hotel)
    
    for rule in rules:
        ot_hours = Decimal('0')
        
        if rule.days_of_week:
            allowed_days = [int(d) for d in rule.days_of_week.split(',')]
            if shift.date.weekday() not in allowed_days:
                continue
        
        if rule.start_time and rule.end_time:
            shift_start = datetime.combine(shift.date, shift.start_time)
            shift_end = datetime.combine(shift.date, shift.end_time)
            if shift_end < shift_start:
                shift_end += timedelta(days=1)
            
            rule_start = datetime.combine(shift.date, rule.start_time)
            rule_end = datetime.combine(shift.date, rule.end_time)
            if rule_end < rule_start:
                rule_end += timedelta(days=1)
            
            overlap_start = max(shift_start, rule_start)
            overlap_end = min(shift_end, rule_end)
            
            if overlap_end > overlap_start:
                diff = overlap_end - overlap_start
                ot_hours = Decimal(str(round(diff.total_seconds() / 3600, 2)))
        else:
            ot_hours = Decimal(str(shift.scheduled_hours))
        
        if ot_hours > 0:
            amount = ot_hours * shift.employee.hourly_wage * rule.multiplier
            overtimes.append({'rule': rule, 'hours': ot_hours, 'amount': round(amount, 2)})
            ShiftOvertime.objects.get_or_create(
                shift=shift, rule=rule,
                defaults={'hours': ot_hours, 'amount': amount}
            )
    
    return overtimes