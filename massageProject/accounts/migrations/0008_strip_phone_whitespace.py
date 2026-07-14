from django.db import migrations


def strip_phone_whitespace(apps, schema_editor):
    CustomUser = apps.get_model('accounts', 'CustomUser')
    for user in CustomUser.objects.all():
        stripped = user.phone_number.strip()
        if stripped == user.phone_number:
            continue
        # Skip if a clean duplicate already exists — merging accounts is a
        # manual decision, not something a migration should do silently.
        if CustomUser.objects.exclude(pk=user.pk).filter(phone_number=stripped).exists():
            continue
        user.phone_number = stripped
        user.save(update_fields=['phone_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_emailotp'),
    ]

    operations = [
        migrations.RunPython(strip_phone_whitespace, migrations.RunPython.noop),
    ]
