from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from staff.models import Shift

class Command(BaseCommand):
    help = 'Αυτόματη ολοκλήρωση βαρδιών που πέρασαν (αν δεν έχουν actual times)'

    def handle(self, *args, **kwargs):
        yesterday = timezone.now().date() - timedelta(days=1)
        shifts = Shift.objects.filter(
            date__lte=yesterday,
            status='scheduled'
        )
        
        completed = 0
        for shift in shifts:
            # Auto-complete με scheduled times
            shift.actual_start = shift.start_time
            shift.actual_end = shift.end_time
            shift.status = 'completed'
            shift.save()
            completed += 1
        
        self.stdout.write(self.style.SUCCESS(f'Ολοκληρώθηκαν {completed} βάρδιες'))