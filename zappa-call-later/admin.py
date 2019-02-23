from django.contrib import admin
from .models import CallLater


def check_now(modeladmin, request, queryset):
    for call_later in queryset:
        call_later.check_individual()


class CallLaterAdmin(admin.ModelAdmin):
    all_fields = [field.name for field in CallLater._meta.fields if
                   field.name not in ["args", "kwargs", "function"]]

    actions = [check_now, ]  # <-- Add the list action function here


admin.site.register(CallLater, CallLaterAdmin)


