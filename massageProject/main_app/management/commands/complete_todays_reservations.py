import logging
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone
import sentry_sdk

from massageProject.main_app.models import Reservation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Mark today's still-active reservations whose appointment has already "
        'ended as completed. Meant for cron, run in the evening.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would be completed without changing anything.',
        )

    def handle(self, *args, **options):
        now = timezone.localtime()
        reservations = Reservation.objects.active().filter(date__lte=now.date())
        # Skip an appointment still in progress if cron runs early.
        due = [
            r for r in reservations
            if timezone.make_aware(datetime.combine(r.date, r.end_time)) <= now
        ]

        if options['dry_run']:
            self.stdout.write(f'{len(due)} reservation(s) to complete')
            return

        completed = failed = 0
        for reservation in due:
            try:
                reservation.change_status(Reservation.STATUS_COMPLETED)
                completed += 1
            except Exception as exc:
                failed += 1
                logger.warning('Could not complete reservation %s', reservation.pk, exc_info=True)
                sentry_sdk.capture_exception(exc, extra={
                    'reservation_pk': reservation.pk, 'operation': 'complete_todays_reservations',
                })

        self.stdout.write(f'Completed {completed} reservation(s), {failed} failed')
