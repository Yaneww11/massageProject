# Generated by Django 5.1.3 on 2024-12-11 21:17

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='phone_number',
            field=models.CharField(help_text='089999999', max_length=15, unique=True, validators=[django.core.validators.RegexValidator(message='Please correct valid phone number', regex='^(\\+359|0)?8[789]\\d{7}$')]),
        ),
    ]
