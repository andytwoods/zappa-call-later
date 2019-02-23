from django.core import management


def now():
    management.call_command('check_for_tasks')
