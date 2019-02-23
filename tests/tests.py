from datetime import timedelta
from random import random, randint
from unittest import TestCase

from django.core.exceptions import ValidationError
from django.utils import timezone

from src import models
from src.models import CallLater, events, check_now, MAX_TIME, test_run


def test_function(_arg1, _arg2, _kwarg1=1, _kwarg2=2):
    return _arg1, _arg2, _kwarg1, _kwarg2


def test_function_advanced():
    test_function_advanced.val += 1
    return True


class TestingZappaCallLater(TestCase):

    def test_picklefield(self):

        call_later = CallLater()
        call_later.function = test_function
        call_later.save()

        self.assertIsNotNone(call_later.function)

        call_later.args = (3, 4)
        call_later.kwargs = {'_kwarg1': 11, '_kwarg2': 22}
        call_later.save()

        try:
            call_later.function()
            self.assertFalse(True)
        except TypeError:
            self.assertIsNotNone('should raise that 2 args missing')

        arg1, arg2, kwarg1, kwarg2 = call_later.function(*call_later.args, **call_later.kwargs)
        self.assertEquals(arg1, 3)
        self.assertEquals(arg2, 4)
        self.assertEquals(kwarg1, 11)
        self.assertEquals(kwarg2, 22)

    def test_call_later(self):

        class Mockedlogger:
            logger_message = []

            @staticmethod
            def error(my_type):
                Mockedlogger.logger_message.append(my_type)

        models.logger = Mockedlogger

        test_function_advanced.val = 0

        time_threshold = timezone.now()

        call_later_once = CallLater()
        call_later_once.function = test_function_advanced
        call_later_once.time_to_run = time_threshold
        call_later_once.repeat = 1
        call_later_once.save()

        # so we can check later it is deleted
        call_later_once_id = call_later_once.id

        self.assertEquals(test_run(call_later_once, time_threshold), events['called_and_destroyed'])

        # check deleted from db
        self.assertEquals(CallLater.objects.filter(id=call_later_once_id).count(), 0)

        call_later_twice = CallLater()
        call_later_twice.function = test_function_advanced
        call_later_twice.time_to_run = time_threshold
        call_later_twice.time_to_stop = None
        call_later_twice.every = timedelta(seconds=1)
        call_later_twice.repeat = 2
        call_later_twice.save()
        self.assertEquals(test_run(call_later_twice, time_threshold), events['will_be_called_in_future_again'])
        call_later_twice = CallLater.objects.get(id=call_later_twice.id)
        self.assertEquals(call_later_twice.time_to_run, time_threshold + call_later_twice.every)
        call_later_twice.time_to_run = time_threshold
        call_later_twice.save()
        self.assertEquals(test_run(call_later_twice, time_threshold), events['called_and_destroyed'])

        call_later_many_but_has_expired_expired = CallLater()
        call_later_many_but_has_expired_expired.function = test_function_advanced
        call_later_many_but_has_expired_expired.time_to_run = time_threshold
        call_later_many_but_has_expired_expired.time_to_stop = time_threshold - timedelta(hours=1)
        call_later_many_but_has_expired_expired.repeat = 2
        call_later_many_but_has_expired_expired.every = timedelta(seconds=1)
        call_later_many_but_has_expired_expired.save()
        self.assertEquals(test_run(call_later_many_but_has_expired_expired, time_threshold), events['called_and_expired'])

        call_later_repeat = CallLater()

        test_function_advanced.val = 0
        call_later_repeat.function = test_function_advanced
        call_later_repeat.time_to_run = time_threshold
        call_later_repeat.repeat = 2

        def shoud_raise_error():
            call_later_repeat.save()
        self.assertRaises(ValidationError, shoud_raise_error)

        every = timedelta(seconds=2)
        call_later_repeat.every = every
        call_later_repeat.save()

        self.assertEquals(test_function_advanced.val, 0)

        check_now(time_threshold)
        self.assertEquals(test_function_advanced.val, 1)
        call_later_repeat = CallLater.objects.get(id=call_later_repeat.id)
        self.assertEquals(call_later_repeat.repeat, 1)

        # repeat the above. Note though that we added 2 seconds onto when the f should next
        # be called. The function should now NOT be called
        check_now(time_threshold)
        self.assertEquals(test_function_advanced.val, 1)
        call_later_repeat = CallLater.objects.get(id=call_later_repeat.id)
        self.assertEquals(call_later_repeat.repeat, 1)

        # adding 2 seconds onto the time the checker is next called...
        check_now(time_threshold+timedelta(seconds=2))
        # below verifies f has been called
        self.assertEquals(test_function_advanced.val, 2)
        # and as count = 0, the function should have been deleted:
        self.assertEquals(CallLater.objects.filter(id=call_later_repeat.id).count(), 0)

        # when does not run within MAX_TIME
        CallLater.objects.all().delete()
        call_later_expires = CallLater()
        retry_count = call_later_expires.timeout_retries
        call_later_expires.when_check_if_failed = time_threshold + timedelta(seconds=MAX_TIME)
        call_later_expires.time_to_run = time_threshold - timedelta(seconds=1)



        call_later_expires.function = raise_an_error
        call_later_expires.save()
        call_later_expires_id = call_later_expires.id

        Mockedlogger.logger_message = []

        check_now(time_threshold + timedelta(seconds=MAX_TIME))

        call_later_expires = CallLater.objects.get(id=call_later_expires_id)

        self.assertTrue(models.events['failed to run before expired'] in Mockedlogger.logger_message[0])
        self.assertEquals(CallLater.objects.count(), 1)

        self.assertEquals(call_later_expires.timeout_retries, retry_count-1)

        self.assertEquals(call_later_expires.problem, False)

        call_later_expires.when_check_if_failed = time_threshold + timedelta(seconds=MAX_TIME)
        call_later_expires.timeout_retries=0
        call_later_expires.save()
        Mockedlogger.logger_message = []
        check_now(time_threshold + timedelta(seconds=MAX_TIME))

        self.assertTrue(models.events['repeatedly failed'] in Mockedlogger.logger_message[0])
        call_later_expires = CallLater.objects.get(id=call_later_expires.id)

        self.assertEquals(call_later_expires.timeout_retries, 0)
        self.assertEquals(call_later_expires.problem, True)

    def test_many(self):
        CallLater.objects.all().delete()

        class Mockedlogger:
            logger_message = []

            @staticmethod
            def error(my_type):
                Mockedlogger.logger_message.append(my_type)

        models.logger = Mockedlogger

        time_start = timezone.now()

        how_many = 40

        time_period = 10

        local_success_count = 0
        local_fail_count = 0

        for i in range(0, how_many):
            call_later = CallLater()

            call_later.time_to_run = time_start + timedelta(seconds=randint(0, time_period-1))
            if random() > .5:
                local_success_count += 1
                call_later.function = SuccessFailsCount.add_success
            else:
                local_fail_count += 1
                call_later.function = SuccessFailsCount.add_fail

            call_later.function.args = (1, 2)
            call_later.save()

        for i in range(0, time_period):
            check_now(time_start+timedelta(seconds=i))

        self.assertEquals(SuccessFailsCount.successes, local_success_count)
        self.assertEquals(CallLater.objects.all().count(), local_fail_count)


class SuccessFailsCount:
    successes = 0
    fails = 0

    @staticmethod
    def add_success():
        SuccessFailsCount.successes += 1

    @staticmethod
    def add_fail():
        SuccessFailsCount.fails += 1
        raise Exception()


def raise_an_error():
    raise ValueError('A very specific bad thing happened')