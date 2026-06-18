from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission

class Command(BaseCommand):
    help = 'Δημιουργία ομάδων HR και Manager'

    def handle(self, *args, **kwargs):
        hr_group, created = Group.objects.get_or_create(name='HR')
        if created:
            all_perms = Permission.objects.all()
            hr_group.permissions.set(all_perms)
            self.stdout.write(self.style.SUCCESS('Δημιουργήθηκε ομάδα HR'))
        
        manager_group, created = Group.objects.get_or_create(name='Manager')
        if created:
            self.stdout.write(self.style.SUCCESS('Δημιουργήθηκε ομάδα Manager'))
        
        self.stdout.write(self.style.SUCCESS('Ομάδες έτοιμες!'))