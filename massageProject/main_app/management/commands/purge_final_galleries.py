from django.core.management.base import BaseCommand
from django.db import connection, transaction

from massageProject.main_app.models import Gallery, Reservation

FINAL_GALLERY_TYPE = 'final'


class Command(BaseCommand):
    help = (
        'Delete every legacy final Gallery with its images (the bucket objects go with '
        'them via the Image pre_delete signals). Run once per deployment, BEFORE `migrate` '
        'drops Reservation.final_gallery. Existing finals_delivered_at stamps are kept.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print the count and the affected reservations without deleting anything.',
        )

    def _linked_reservations(self):
        """(reservation id, phase) for every reservation still pointing at a final
        gallery. Raw SQL: the model no longer has the field, but the column
        exists until the migration that drops it has run."""
        table = Reservation._meta.db_table
        with connection.cursor() as cursor:
            columns = {c.name for c in connection.introspection.get_table_description(cursor, table)}
            if 'final_gallery_id' not in columns:
                return []
            cursor.execute(
                f'SELECT id, finals_delivered_at IS NOT NULL FROM {table} '
                f'WHERE final_gallery_id IS NOT NULL ORDER BY id'
            )
            return [(pk, 'finals_delivered' if delivered else 'finals_ready') for pk, delivered in cursor.fetchall()]

    def _detach_reservations(self):
        # Without this the database still holds the reference, and the old
        # CASCADE semantics could take the reservation down with its gallery.
        table = Reservation._meta.db_table
        with connection.cursor() as cursor:
            columns = {c.name for c in connection.introspection.get_table_description(cursor, table)}
            if 'final_gallery_id' in columns:
                cursor.execute(f'UPDATE {table} SET final_gallery_id = NULL WHERE final_gallery_id IS NOT NULL')

    def handle(self, *args, **options):
        galleries = Gallery.objects.filter(gallery_type=FINAL_GALLERY_TYPE)
        linked = self._linked_reservations()
        ready = sum(1 for _pk, phase in linked if phase == 'finals_ready')
        count = galleries.count()

        if options['dry_run']:
            self.stdout.write(f'{count} final gallery(ies) would be deleted')
            for pk, phase in linked:
                self.stdout.write(f'reservation {pk}: {phase}')
            self.stdout.write(f'{ready} finals_ready reservation(s) would lose their files')
            return

        with transaction.atomic():
            self._detach_reservations()
            for gallery in galleries:
                gallery.delete()
        self.stdout.write(f'Deleted {count} final gallery(ies)')
        self.stdout.write(f'{ready} finals_ready reservation(s) lost their files')
