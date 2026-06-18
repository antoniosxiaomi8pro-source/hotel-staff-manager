from django.core.management.base import BaseCommand
from staff.models import Employee, EmployeeDepartment, Department

class Command(BaseCommand):
    help = 'Δημιουργία EmployeeDepartment για υπάλληλους χωρίς τμήμα'

    def handle(self, *args, **kwargs):
        employees = Employee.objects.filter(departments__isnull=True, is_active=True)
        
        created = 0
        for emp in employees:
            dept = Department.objects.first()
            if dept:
                EmployeeDepartment.objects.create(
                    employee=emp,
                    department=dept,
                    hours_per_day=8.00,
                    is_primary=True
                )
                created += 1
                self.stdout.write(f"✅ {emp.full_name} → {dept.name}")
        
        self.stdout.write(self.style.SUCCESS(f'Δημιουργήθηκαν {created} συνδέσεις!'))