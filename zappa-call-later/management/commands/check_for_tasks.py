from django.core.management.base import BaseCommand
from src.models import check_now


class Command(BaseCommand):
    help = 'check_now whether tasks are scheduled to run, and set up their running via async zappa calls'

    def handle(self, *args, **options):
        check_now()
        self.stdout.write(self.style.SUCCESS('Checked for scheduled tasks"'))


