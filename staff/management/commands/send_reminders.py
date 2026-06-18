from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from staff.models import Shift
from staff.email_utils import send_shift_notification

class Command(BaseCommand):
    help = 'Αποστολή υπενθυμίσεων για αυριανές βάρδιες'

    def handle(self, *args, **kwargs):
        tomorrow = timezone.now().date() + timedelta(days=1)
        shifts = Shift.objects.filter(date=tomorrow, status='scheduled').select_related('employee')
        
        sent = 0
        for shift in shifts:
            if send_shift_notification(shift, action='reminder'):
                sent += 1
        
        self.stdout.write(self.style.SUCCESS(f'Στάλθηκαν {sent} υπενθυμίσεις'))