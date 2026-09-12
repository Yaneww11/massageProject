from django.db import migrations

from massageProject.main_app.theme import COLOR_PRESETS


def _apply(apps, preset_key):
    SiteConfiguration = apps.get_model('main_app', 'SiteConfiguration')
    config = SiteConfiguration.objects.first()
    if config is None:
        return
    for field, value in COLOR_PRESETS[preset_key].items():
        if field != 'label':
            setattr(config, field, value)
    config.color_preset = preset_key
    config.save()


def apply_gallery_black(apps, schema_editor):
    _apply(apps, 'gallery_black')


def restore_warm_earth(apps, schema_editor):
    _apply(apps, 'warm_earth')


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0054_alter_siteconfiguration_accent_color_and_more'),
    ]

    operations = [
        migrations.RunPython(apply_gallery_black, restore_warm_earth),
    ]
