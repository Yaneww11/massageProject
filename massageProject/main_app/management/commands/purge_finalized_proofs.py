import logging

from django.core.management.base import BaseCommand
import sentry_sdk

from massageProject.main_app.models import Reservation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Delete the proofing photos a client did not keep and the watermarked proof '
        'derivatives of every photo, for every reservation finalised since the last '
        'run. Meant for cron: purging a full gallery is roughly four storage round '
        'trips per photo, far too slow to run inside the finalise request.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would be purged without deleting anything.',
        )

    def handle(self, *args, **options):
        pending = Reservation.all_objects.filter(
            proofing_finalized_at__isnull=False, proofs_purged_at__isnull=True,
        ).order_by('proofing_finalized_at')

        purged = failed = total_images = 0
        for reservation in pending:
            if options['dry_run']:
                count = reservation.unmarked_proof_count()
                self.stdout.write(f'reservation {reservation.pk}: would purge {count} photo(s)')
                total_images += count
                continue
            try:
                # One reservation at a time: a bucket error on one client's
                # gallery must not abandon everyone else queued behind it. The
                # next run picks it up again, since proofs_purged_at is only
                # stamped on success.
                total_images += reservation.purge_finalized_proofs()
                purged += 1
            except Exception as exc:
                failed += 1
                logger.warning('Could not purge proofs for reservation %s', reservation.pk, exc_info=True)
                sentry_sdk.capture_exception(exc, extra={
                    'reservation_pk': reservation.pk, 'operation': 'purge_finalized_proofs',
                })

        if options['dry_run']:
            self.stdout.write(f'{pending.count()} reservation(s) pending, {total_images} photo(s) to purge')
        else:
            self.stdout.write(f'Purged {total_images} photo(s) across {purged} reservation(s), {failed} failed')
