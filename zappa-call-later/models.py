import inspect
import json
from datetime import timedelta
from logging import getLogger

import pytz
from dateutil.parser import parse
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers import serialize
from django.utils import timezone
from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from picklefield import PickledObjectField

logger = getLogger(__name__)

# used for testing purposes
events = {
    'called_and_destroyed': 'deleted after 1 call',
    'called': 'called',
    'called_and_expired': 'called_and_expired',
    'will_be_called_in_future_again': 'call in future',
    'failed to run so must be rerun': 'failed to run so rerun',
    'waiting': 'still waiting to run',
    'failed to run before expired': 'call later function failed to run within allotted time!',
    'error calling pickled function': 'error calling pickled function, or problem with polling',
    'expired function was eventually called': 'expired yet called',
    'repeatedly failed': 'repeatedly timed out, given up!',
}

MAX_TIME = 60 * 10  # 10 minutes


def far_future_fail_timeout():
    return timezone.now() + timedelta(days=365)


def realistic_timeout(time_threshold):
    return time_threshold + timedelta(MAX_TIME)


@python_2_unicode_compatible
class CallLater(models.Model):
    name = models.CharField(max_length=64, default='', editable=True, verbose_name=u'additional lookup field')
    time_to_run = models.DateTimeField(default=timezone.now)
    time_to_stop = models.DateTimeField(null=True, blank=True)
    function = PickledObjectField()
    args = PickledObjectField(null=True)
    kwargs = PickledObjectField(null=True)
    repeat = models.PositiveIntegerField(default=1)
    every = models.DurationField(null=True, blank=True)
    when_check_if_failed = models.DateTimeField(default=far_future_fail_timeout)
    retries = models.PositiveIntegerField(default=3)
    timeout_retries = models.PositiveIntegerField(default=2)
    problem = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # (<django.db.models.fields.PositiveIntegerField>,) is returned if self.repeat not set
        # I assume i must save() model before default value is given
        if self.every is None and type(self.repeat) is int and self.repeat is not 1:
            raise ValidationError('you must set a repeat time (via every=[timedelta]) if you want a function called many times'
                                  ' (each time after current time + repeat')
        super(CallLater, self).save(*args, **kwargs)

    def check_individual(self):
        preprocess_instance(self, timezone.now())



#used for testing
def to_check(time_threshold=timezone.now()):
    to_run = CallLater.objects.filter(time_to_run__lte=time_threshold,
                                      when_check_if_failed__gt=time_threshold,
                                      problem=False).count()
    timedout_again_to_run = CallLater.objects.filter(when_check_if_failed__lte=time_threshold,
                                                     problem=False).count()

    return 'to_run=' + str(to_run)+', timedout_again_to_run='+str(timedout_again_to_run)


def check_now(timenow=timezone.now()):

    # what happens if there is a huge number of items and all cant be run within 30 time period?
    # perhaps batch off groups of x to zappa.async

    for to_run in CallLater.objects.filter(time_to_run__lte=timenow,
                                           when_check_if_failed__gt=timenow,
                                           problem=False):
        preprocess_instance(to_run, timenow)

    for timedout_again_to_run in CallLater.objects.filter(when_check_if_failed__lte=timenow,
                                                          problem=False):
        if timedout_again_to_run.timeout_retries == 0:
            timedout_again_to_run.problem = True
            timedout_again_to_run.save()
            log_error(events['repeatedly failed'], timedout_again_to_run)
            continue
        else:
            log_error(events['failed to run before expired'], timedout_again_to_run)

        timedout_again_to_run.timeout_retries -= 1
        preprocess_instance(timedout_again_to_run, timenow)


def preprocess_instance(to_run, time_threshold):
    to_run.when_check_if_failed = realistic_timeout(time_threshold)
    to_run.save()
    run(to_run.id, time_threshold.strftime("%Y-%m-%d %H:%M:%S"))


def log_error(message, instance):
    # serialising model instance
    # https://stackoverflow.com/questions/757022/how-do-you-serialize-a-model-instance-in-django
    data = serialize('json', [instance, ])
    struct = json.loads(data)
    try:
        # replace long String64 function with useful info
        f = instance.function
        signature = str(inspect.signature(f))
        if hasattr(f, 'args'):
            signature += ', args='+str(f.args)
        if hasattr(f, 'kwargs'):
            signature += ', kwargs=' + str(f.kwargs)

        struct[0]['fields']['function'] = str(f.__module__+"."+f.__name__ + signature)

    except Exception:
        pass
    data = json.dumps(struct[0])
    logger.error(message + ' ' + data)


def test_run(call_later, time_threshold):
    return run(call_later.id, time_threshold.astimezone().isoformat())


# using id to avoid pickle issues
#  @task
def run(call_later_id, time_threshold_txt):
    time_threshold = parse(time_threshold_txt)

    try:
        call_later = CallLater.objects.get(id=call_later_id)
    except CallLater.DoesNotExist:
        log_error(events['expired function was eventually called'], call_later)
        return
    try:
        _args = call_later.args or ()
    except AttributeError:
        _args = ()
    try:
        _kwargs = call_later.kwargs or {}
    except AttributeError:
        _kwargs = {}

    #attempt to call the function here
    try:
        call_later.function(*_args, **_kwargs)
    except TypeError as e:
        pass
        #  has been manually deleted
    except Exception as e:
        if call_later.retries == 0:
            call_later.problem = True
            log_error(events['error calling pickled function'] + str(e), call_later)
            return
        call_later.retries -= 1
        call_later.save()
        return

    if call_later.repeat <= 1:
        call_later.delete()
        return events['called_and_destroyed']  # for testing purposes

    # I assume i must save() model before default value is given
    if type(call_later.time_to_stop) != tuple and call_later.time_to_stop is not None\
            and call_later.time_to_stop <= time_threshold:
        call_later.delete()
        return events['called_and_expired']

    if call_later.every is not None:
        call_later.repeat -= 1

        time_to_run = time_threshold + call_later.every
        if time_to_run.tzinfo is None or time_to_run.tzinfo.utcoffset(time_to_run) is None:
            time_to_run = pytz.timezone(settings.TIME_ZONE).localize(time_to_run)

        call_later.time_to_run = time_to_run
        call_later.when_check_if_failed = far_future_fail_timeout()
        call_later.save()
        return events['will_be_called_in_future_again']

    return events['called']




