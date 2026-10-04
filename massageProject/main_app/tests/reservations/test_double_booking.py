import threading
from datetime import time, timedelta

from django import db
from django.db import IntegrityError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from massageProject.main_app.models import Reservation
from massageProject.main_app.tests.reservations.helpers import ReservationAuditFixTestBase


class DoubleBookingRaceConditionTest(ReservationAuditFixTestBase, TransactionTestCase):
    """1.1 — concurrent bookings for the identical slot must not both succeed."""

    def setUp(self):
        self._make_base_objects()

    def test_concurrent_identical_slot_bookings_only_one_succeeds(self):
        booking_date = (timezone.now() + timedelta(days=3)).date()
        results = []

        def book():
            try:
                Reservation.objects.create(
                    service=self.service,
                    specialist=self.specialist,
                    user=self.user,
                    date=booking_date,
                    time=time(10, 0),
                )
                results.append('ok')
            except Exception as exc:
                results.append(type(exc).__name__)
            finally:
                db.connections.close_all()

        t1 = threading.Thread(target=book)
        t2 = threading.Thread(target=book)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(results.count('ok'), 1, f"expected exactly one booking to succeed, got: {results}")
        self.assertEqual(
            Reservation.objects.filter(date=booking_date, time=time(10, 0), status=Reservation.STATUS_ACTIVE).count(),
            1,
        )


class UniqueActiveSlotConstraintTest(ReservationAuditFixTestBase, TestCase):
    """Defense-in-depth DB constraint from 1.1."""

    def setUp(self):
        self._make_base_objects()

    def test_db_constraint_blocks_duplicate_active_slot_bypassing_clean(self):
        booking_date = (timezone.now() + timedelta(days=3)).date()
        Reservation.objects.create(
            service=self.service, specialist=self.specialist, user=self.user,
            date=booking_date, time=time(10, 0),
        )
        dup = Reservation(
            service=self.service, specialist=self.specialist, user=self.user,
            date=booking_date, time=time(10, 0),
        )
        with self.assertRaises(IntegrityError):
            Reservation.objects.bulk_create([dup])
