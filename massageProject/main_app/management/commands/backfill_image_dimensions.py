import logging

from PIL import Image as PILImage
from django.core.management.base import BaseCommand
from django.db.models import Q

from massageProject.main_app.models import Image

logger = logging.getLogger(__name__)


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
                    # The stored file's raw size, read from the header only so
                    # the pixels are never decoded. EXIF orientation is ignored:
                    # the proof derivative is not transposed either.
                    width, height = img.size
            except Exception:
                failed += 1
                logger.warning('Could not read dimensions of Image %s (%s)', image.pk, image.image.name, exc_info=True)
                self.stderr.write(f'Image {image.pk}: could not read {image.image.name!r}')
                continue
            Image.objects.filter(pk=image.pk).update(width=width, height=height)
            updated += 1

        self.stdout.write(f'{updated} updated, {skipped} skipped, {failed} failed')
