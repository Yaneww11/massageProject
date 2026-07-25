from django.db import migrations


def forwards(apps, schema_editor):
    Gallery = apps.get_model('main_app', 'Gallery')
    Image = apps.get_model('main_app', 'Image')
    GalleryImage = apps.get_model('main_app', 'GalleryImage')
    GalleryAlbum = apps.get_model('main_app', 'GalleryAlbum')
    AlbumPhoto = apps.get_model('main_app', 'AlbumPhoto')
    HomePage = apps.get_model('main_app', 'HomePage')
    Reservation = apps.get_model('main_app', 'Reservation')

    # (a) tag existing Gallery rows by role
    homepage_ids = set(HomePage.objects.values_list('gallery_id', flat=True))
    Gallery.objects.filter(pk__in=homepage_ids).update(gallery_type='homepage')

    reservation_ids = set(
        Reservation.objects.exclude(gallery=None).values_list('gallery_id', flat=True)
    ) - homepage_ids
    Gallery.objects.filter(pk__in=reservation_ids).update(gallery_type='reservation')

    # copy the merged text field for every pre-existing Gallery row. Historical
    # models from apps.get_model() don't have modeltranslation's proxy
    # descriptors active, so read/write the physical _bg/_en columns directly.
    for g in Gallery.objects.all():
        g.description_bg = g.short_description_bg
        g.description_en = g.short_description_en
        g.save(update_fields=['description_bg', 'description_en'])

    # (c)/(d) convert GalleryImage M2M rows -> direct Image.gallery FK, per gallery
    for gallery in Gallery.objects.all():
        links = list(GalleryImage.objects.filter(gallery=gallery).order_by('pk'))
        for idx, link in enumerate(links):
            img = link.image
            if img.gallery_id is None:
                img.gallery_id = gallery.pk
                img.order = idx
                img.save(update_fields=['gallery', 'order'])
            else:
                # image already claimed by an earlier gallery membership ->
                # duplicate the row (new model can't share images)
                Image.objects.create(
                    gallery=gallery, order=idx, image=img.image,
                    alt_text=img.alt_text, alt_text_bg=img.alt_text_bg, alt_text_en=img.alt_text_en,
                )

    # true orphans: an Image never linked via any GalleryImage row
    Image.objects.filter(gallery=None).delete()

    # (b) copy GalleryAlbum -> Gallery, AlbumPhoto -> Image
    for album in GalleryAlbum.objects.all():
        gallery = Gallery.objects.create(
            gallery_type='album',
            title=album.title, title_bg=album.title_bg, title_en=album.title_en,
            description=album.description, description_bg=album.description_bg,
            description_en=album.description_en,
            slug=album.slug, order=album.order,
        )
        for photo in AlbumPhoto.objects.filter(album=album).order_by('order'):
            Image.objects.create(
                gallery=gallery, order=photo.order, image=photo.image,
                alt_text=photo.alt_text, alt_text_bg=photo.alt_text_bg, alt_text_en=photo.alt_text_en,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0036_gallery_merge_schema_add'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
