from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone

class Hotel(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

class Department(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=100)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_departments')
    
    class Meta:
        unique_together = ['hotel', 'name']
    
    def __str__(self):
        return f"{self.hotel.name} - {self.name}"

class Employee(models.Model):
    CONTRACT_TYPES = [
        ('full_time', 'Πλήρης Απασχόληση'),
        ('part_time', 'Μερική Απασχόληση'),
        ('seasonal', 'Εποχιακός'),
        ('contractor', 'Εξωτερικός Συνεργάτης'),
    ]
    
    SALARY_TYPES = [
        ('hourly', 'Ωρομίσθιος'),
        ('monthly', 'Μηνιαίος'),
        ('daily', 'Ημερομίσθιος'),
        ('none', 'Χωρίς Υπολογισμό'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=100)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPES, default='full_time')
    
    # ΜΙΣΘΟΔΟΣΙΑ - Προαιρετικά
    salary_type = models.CharField(max_length=20, choices=SALARY_TYPES, default='none')
    hourly_wage = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)], blank=True, null=True)
    monthly_salary = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], blank=True, null=True)
    daily_wage_fixed = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)], blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    date_joined = models.DateField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def daily_calculated_wage(self):
        """Υπολογισμός ημερήσιου μισθού"""
        if self.salary_type == 'monthly' and self.monthly_salary:
            # 5ήμερο = ~22 εργάσιμες μέρες/μήνα
            return round(float(self.monthly_salary) / 22, 2)
        elif self.salary_type == 'daily' and self.daily_wage_fixed:
            return float(self.daily_wage_fixed)
        elif self.salary_type == 'hourly' and self.hourly_wage:
            return round(float(self.hourly_wage) * 8, 2)  # 8 ώρες default
        return 0

class EmployeeDepartment(models.Model):
    """Many-to-Many: Υπάλληλος σε πολλά τμήματα"""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='departments')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='employee_departments')
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    hours_per_day = models.DecimalField(max_digits=4, decimal_places=2, default=8.00)
    is_primary = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['employee', 'department']
        ordering = ['-is_primary', '-start_date']
    
    def __str__(self):
        status = "Ενεργό" if not self.end_date else f"Έως {self.end_date}"
        return f"{self.employee} @ {self.department} ({self.hours_per_day}h) - {status}"
    
    @property
    def is_active_now(self):
        if self.end_date and self.end_date < timezone.now().date():
            return False
        return True

class Shift(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Προγραμματισμένη'),
        ('confirmed', 'Επιβεβαιωμένη'),
        ('completed', 'Ολοκληρωμένη'),
        ('cancelled', 'Ακυρωμένη'),
    ]
    
    SHIFT_TYPES = [
        ('morning', 'Πρωινή (07:00-15:00)'),
        ('afternoon', 'Απογευματινή (15:00-23:00)'),
        ('night', 'Βραδινή (23:00-07:00)'),
        ('split', 'Σπαστή'),
        ('custom', 'Custom'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='shifts')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='shifts')
    employee_department = models.ForeignKey(EmployeeDepartment, on_delete=models.SET_NULL, null=True, blank=True)
    
    date = models.DateField()
    shift_type = models.CharField(max_length=20, choices=SHIFT_TYPES, default='morning')
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_shifts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    actual_start = models.TimeField(null=True, blank=True)
    actual_end = models.TimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['date', 'start_time']
        # Αφαιρέθηκε το unique_together για να επιτρέπονται πολλές βάρδιες/ημέρα
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.date} ({self.start_time}-{self.end_time})"
    
    @property
    def scheduled_hours(self):
        from datetime import datetime, timedelta
        start = datetime.combine(self.date, self.start_time)
        end = datetime.combine(self.date, self.end_time)
        if end < start:
            end += timedelta(days=1)
        diff = end - start
        return round(diff.total_seconds() / 3600, 2)
    
    @property
    def actual_hours(self):
        if self.actual_start and self.actual_end:
            from datetime import datetime, timedelta
            if isinstance(self.actual_start, str):
                start_time = datetime.strptime(self.actual_start, "%H:%M").time()
            else:
                start_time = self.actual_start
            if isinstance(self.actual_end, str):
                end_time = datetime.strptime(self.actual_end, "%H:%M").time()
            else:
                end_time = self.actual_end
            start = datetime.combine(self.date, start_time)
            end = datetime.combine(self.date, end_time)
            if end < start:
                end += timedelta(days=1)
            diff = end - start
            return round(diff.total_seconds() / 3600, 2)
        return None

    @property
    def daily_wage(self):
        """Υπολογισμός ημερομισθίου βάσει τύπου μισθοδοσίας"""
        hours = self.actual_hours or self.scheduled_hours
        
        if self.employee.salary_type == 'none':
            return 0
        
        elif self.employee.salary_type == 'monthly' and self.employee.monthly_salary:
            # Μηνιαίος / 22 μέρες / 8 ώρες = ωρομίσθιο
            hourly = float(self.employee.monthly_salary) / 22 / 8
            return round(hours * hourly, 2)
        
        elif self.employee.salary_type == 'daily' and self.employee.daily_wage_fixed:
            # Ημερομίσθιο × (ώρες βάρδιας / 8)
            ratio = hours / 8
            return round(float(self.employee.daily_wage_fixed) * ratio, 2)
        
        elif self.employee.salary_type == 'hourly' and self.employee.hourly_wage:
            return round(hours * float(self.employee.hourly_wage), 2)
        
        return 0

class OvertimeRule(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=1.5)
    days_of_week = models.CharField(max_length=20, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    is_holiday = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.hotel.name} - {self.name} ({self.multiplier}x)"

class ShiftOvertime(models.Model):
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='overtimes')
    rule = models.ForeignKey(OvertimeRule, on_delete=models.CASCADE)
    hours = models.DecimalField(max_digits=4, decimal_places=2)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    
    def __str__(self):
        return f"{self.shift} - {self.rule.name}: {self.hours}h"

class ShiftTemplate(models.Model):
    """Προκαθορισμένες βάρδιες ανά τμήμα (admin-configurable)"""
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='shift_templates')
    name = models.CharField(max_length=100)  # π.χ. "Πρωινό Service", "Setup", "Bar Shift"
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['start_time']
        unique_together = ['department', 'name']
    
    def __str__(self):
        return f"{self.department.name} - {self.name} ({self.start_time}-{self.end_time})"

class GlobalShiftTemplate(models.Model):
    """Templates που εφαρμόζονται σε ΟΛΑ τα ξενοδοχεία"""
    name = models.CharField(max_length=100)  # π.χ. "Πρωινό Service"
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['start_time']
    
    def __str__(self):
        return f"{self.name} ({self.start_time}-{self.end_time})"


class DailyHotelStats(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE)
    date = models.DateField()
    
    # Occupancy
    total_rooms = models.PositiveIntegerField(default=0)
    occupied_rooms = models.PositiveIntegerField(default=0)
    check_ins = models.PositiveIntegerField(default=0)
    check_outs = models.PositiveIntegerField(default=0)
    
    # Revenue (NET)
    room_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fb_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    extras_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Staffing (auto-calculated)
    staff_count = models.PositiveIntegerField(default=0)
    total_wages = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Metadata
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    entered_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['hotel', 'date']
        ordering = ['-date']
        verbose_name = "Ημερήσια Στατιστικά"
        verbose_name_plural = "Ημερήσια Στατιστικά"
    
    
    @property
    def total_revenue(self):
        return self.room_revenue + self.fb_revenue + self.extras_revenue
    
    @property
    def labor_cost_ratio(self):
        if self.total_revenue == 0:
            return 0
        return round((self.total_wages / self.total_revenue) * 100, 1)