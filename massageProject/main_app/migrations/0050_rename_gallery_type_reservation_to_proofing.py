from django.db import migrations


def rename_reservation_to_proofing(apps, schema_editor):
    Gallery = apps.get_model('main_app', 'Gallery')
    Gallery.objects.filter(gallery_type='reservation').update(gallery_type='proofing')


def rename_proofing_to_reservation(apps, schema_editor):
    Gallery = apps.get_model('main_app', 'Gallery')
    Gallery.objects.filter(gallery_type='proofing').update(gallery_type='reservation')


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0049_final_gallery_and_phase'),
    ]

    operations = [
        migrations.RunPython(rename_reservation_to_proofing, rename_proofing_to_reservation),
    ]
