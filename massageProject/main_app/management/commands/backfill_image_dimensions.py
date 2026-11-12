import logging

from PIL import Image as PILImage
from django.core.management.base import BaseCommand
from django.db.models import Q

from massageProject.main_app.models import Image

logger = logging.getLogger(__name__)

EXIF_ORIENTATION = 0x0112
# Orientations that swap width and height (transpose, 90° CW, transverse, 90° CCW).
ROTATED_ORIENTATIONS = {5, 6, 7, 8}


class Command(BaseCommand):
    help = (
        'Fill width/height for Images uploaded before dimensions were recorded. '
        'Run once after deploying; only rows with missing dimensions are read, '
        'so it is safe to re-run. Not part of the migration: reading every file '
        'from storage would block the deploy.'
    )

    def handle(self, *args, **options):
        missing = Q(width__isnull=True) | Q(height__isnull=True)
        skipped = Image.objects.exclude(missing).count()
        updated = failed = 0

        for image in Image.objects.filter(missing).order_by('pk').iterator():
            try:
                with image.image.open('rb') as file, PILImage.open(file) as img:
                    width, height = img.size
                    # Match what the browser shows for a never-converted legacy
                    # file whose EXIF orientation rotates it by 90°; converted
                    # WebP files are already transposed. Read from the header
                    # only, so the pixels are never decoded.
                    if img.getexif().get(EXIF_ORIENTATION) in ROTATED_ORIENTATIONS:
                        width, height = height, width
            except Exception:
                failed += 1
                logger.warning('Could not read dimensions of Image %s (%s)', image.pk, image.image.name, exc_info=True)
                self.stderr.write(f'Image {image.pk}: could not read {image.image.name!r}')
                continue
            Image.objects.filter(pk=image.pk).update(width=width, height=height)
            updated += 1

        self.stdout.write(f'{updated} updated, {skipped} skipped, {failed} failed')
