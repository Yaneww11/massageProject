import logging

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db.models import Q
import sentry_sdk

from massageProject.main_app.models import Image, Reservation

logger = logging.getLogger(__name__)

THUMBNAIL_PREFIX = 'marked_thumbnails/'


class Command(BaseCommand):
    help = (
        'Delete the cached Marked Photos thumbnails of reservations that are '
        'cancelled or whose finals were delivered. Marked photos are never '
        'deleted, so nothing else evicts these. Meant for cron, like '
        'purge_unmarked_proofs.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would be purged without deleting anything.',
        )

    def handle(self, *args, **options):
        # One listing instead of a delete per marked photo of every finished
        # reservation ever: only thumbnails actually in the bucket cost a call.
        try:
            _, filenames = default_storage.listdir(THUMBNAIL_PREFIX)
        except (FileNotFoundError, NotADirectoryError):
            filenames = []
        stored = {
            int(name.split('.')[0]): name
            for name in filenames if name.split('.')[0].isdigit()
        }

        finished_galleries = Reservation.all_objects.filter(
            Q(status=Reservation.STATUS_DELETED) | Q(finals_delivered_at__isnull=False),
            gallery__isnull=False,
        ).values('gallery_id')
        image_ids = Image.objects.filter(
            pk__in=list(stored), gallery_id__in=finished_galleries,
        ).values_list('pk', flat=True)

        if options['dry_run']:
            self.stdout.write(f'{len(image_ids)} thumbnail(s) to purge')
            return

        purged = failed = 0
        for image_id in image_ids:
            try:
                default_storage.delete(THUMBNAIL_PREFIX + stored[image_id])
                purged += 1
            except Exception as exc:
                failed += 1
                logger.warning('Could not delete marked thumbnail of image %s', image_id, exc_info=True)
                sentry_sdk.capture_exception(exc, extra={
                    'image_pk': image_id, 'operation': 'purge_marked_thumbnails',
                })

        self.stdout.write(f'Purged {purged} thumbnail(s), {failed} failed')
