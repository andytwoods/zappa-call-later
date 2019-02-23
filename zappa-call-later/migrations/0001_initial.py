# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-07-12 15:31
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
import picklefield.fields
import src.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CallLater',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='', max_length=64, verbose_name='additional lookup field')),
                ('time_to_run', models.DateTimeField(default=django.utils.timezone.now)),
                ('time_to_stop', models.DateTimeField(blank=True, null=True)),
                ('function', picklefield.fields.PickledObjectField(editable=False)),
                ('args', picklefield.fields.PickledObjectField(editable=False, null=True)),
                ('kwargs', picklefield.fields.PickledObjectField(editable=False, null=True)),
                ('repeat', models.PositiveIntegerField(default=1)),
                ('every', models.DurationField(blank=True, null=True)),
                ('when_check_if_failed', models.DateTimeField(default=src.models.far_future_fail_timeout)),
                ('retries', models.PositiveIntegerField(default=3)),
                ('timeout_retries', models.PositiveIntegerField(default=2)),
                ('problem', models.BooleanField(default=False)),
            ],
        ),
    ]
