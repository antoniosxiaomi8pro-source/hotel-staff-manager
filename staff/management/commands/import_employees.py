import pandas as pd
import math
from django.core.management.base import BaseCommand
from django.db import transaction
from staff.models import Hotel, Department, Employee, EmployeeDepartment

def clean_value(value):
    """Καθαρισμός NaN/None values"""
    if pd.isna(value) or value == 'nan' or value == 'None' or value == '':
        return None
    return value

def clean_decimal(value):
    """Καθαρισμός decimal values"""
    cleaned = clean_value(value)
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None

class Command(BaseCommand):
    help = 'Import employees from Excel/CSV file'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to Excel/CSV file')
        parser.add_argument('--hotel', type=str, required=True, help='Hotel name')
        parser.add_argument('--department', type=str, required=True, help='Department name')

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']
        hotel_name = kwargs['hotel']
        dept_name = kwargs['department']

        # Βρες hotel και department
        try:
            hotel = Hotel.objects.get(name=hotel_name)
        except Hotel.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Hotel "{hotel_name}" δεν βρέθηκε!'))
            return

        try:
            department = Department.objects.get(name=dept_name, hotel=hotel)
        except Department.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Department "{dept_name}" δεν βρέθηκε στο {hotel_name}!'))
            return

        # Διάβασε το αρχείο
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Σφάλμα ανάγνωσης αρχείου: {e}'))
            return

        # Υποχρεωτικές στήλες
        required_columns = ['first_name', 'last_name', 'email']
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            self.stdout.write(self.style.ERROR(f'❌ Λείπουν στήλες: {missing}'))
            self.stdout.write(self.style.WARNING(f'Διαθέσιμες στήλες: {list(df.columns)}'))
            return

        # Import
        created_count = 0
        updated_count = 0
        errors = []

        with transaction.atomic():
            for index, row in df.iterrows():
                try:
                    # Καθαρισμός δεδομένων
                    first_name = clean_value(row['first_name'])
                    last_name = clean_value(row['last_name'])
                    email = clean_value(row['email'])
                    phone = clean_value(row.get('phone', ''))
                    role = clean_value(row.get('role', 'Staff'))
                    contract_type = clean_value(row.get('contract_type', 'full_time'))
                    salary_type = clean_value(row.get('salary_type', 'none'))
                    hourly_wage = clean_decimal(row.get('hourly_wage'))
                    monthly_salary = clean_decimal(row.get('monthly_salary'))
                    daily_wage_fixed = clean_decimal(row.get('daily_wage_fixed'))
                    hours_per_day = clean_decimal(row.get('hours_per_day', 8.0))

                    if not first_name or not last_name or not email:
                        errors.append(f"Σειρά {index + 2}: Λείπουν υποχρεωτικά πεδία")
                        continue

                    # Δημιουργία/Ενημέρωση Employee
                    employee, created = Employee.objects.update_or_create(
                        email=email,
                        defaults={
                            'first_name': str(first_name),
                            'last_name': str(last_name),
                            'phone': str(phone) if phone else '',
                            'role': str(role),
                            'contract_type': str(contract_type),
                            'salary_type': str(salary_type),
                            'hourly_wage': hourly_wage,
                            'monthly_salary': monthly_salary,
                            'daily_wage_fixed': daily_wage_fixed,
                            'is_active': True
                        }
                    )

                    # Δημιουργία EmployeeDepartment
                    emp_dept, dept_created = EmployeeDepartment.objects.update_or_create(
                        employee=employee,
                        department=department,
                        defaults={
                            'hours_per_day': hours_per_day if hours_per_day else 8.0,
                            'is_primary': True
                        }
                    )

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

                except Exception as e:
                    errors.append(f"Σειρά {index + 2}: {e}")

        # Αποτελέσματα
        self.stdout.write(self.style.SUCCESS(f'✅ Import ολοκληρώθηκε!'))
        self.stdout.write(f'  Δημιουργήθηκαν: {created_count}')
        self.stdout.write(f'  Ενημερώθηκαν: {updated_count}')
        
        if errors:
            self.stdout.write(self.style.WARNING(f'  Σφάλματα: {len(errors)}'))
            for error in errors[:5]:
                self.stdout.write(self.style.WARNING(f'    - {error}'))
