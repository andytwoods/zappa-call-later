# zappa-call-later

## Description
A db driven way to run tasks at a future point in time, or at a regular interval, for Django Zappa projects (https://github.com/Miserlou/Zappa).

## Installation
```
pip install zappa-call-later
```
To check for tasks every 4 minutes, add the below to zappa_settings.json:
 
```json



{
  "dev": {
    "keep_warm": false,
    "events": [
      {
        "function": "zappa_call_later.zappa_check.now",
        "expression": "rate(4 minute)"
      }
    ]
  }
}
```
## Usage
Low level currently, where you create and save your tasks straight to db.

```python
def test_function(_arg1, _arg2, _kwarg1=1, _kwarg2=2):
    return _arg1, _arg2, _kwarg1, _kwarg2

call_later = CallLater()
call_later.function = test_function
call_later.args = (3, 4) # for the above function
call_later.kwargs = {'_kwarg1': 11, '_kwarg2': 22} # for the above function
call_later.time_to_run = timezone.now() + timedelta(minutes=8)
call_later.save()
```

You can also repeatedly call your task:
```python
call_later_twice.every = timedelta(seconds=1)
call_later_twice.repeat = 2
```

There are 2 types of failure:
- If a task fails to run, it is run on the next checking event. By default, there are 3 attempts to run a function.
- If a task takes too long to run, it is again run on the next checking event. By default, there are 3 retries.

...the task is labelled as problematic after repeated fails.
