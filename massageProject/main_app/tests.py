from django.test import TestCase
from django.utils import timezone
from massageProject.main_app.models import Massage, Masseur, MessageReservation
from massageProject.accounts.models import CustomUser
from massageProject.main_app.forms import ReservationCreateForm, ReservationEditForm
import datetime

class ReservationValidationTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            phone_number='0888888888',
            email='test@example.com',
            password='password123'
        )
        self.massage = Massage.objects.create(
            name='Test Massage',
            description='Test description',
            price=50.00,
            duration_in_minutes=60,
            short_description='Short desc'
        )
        self.masseur = Masseur.objects.create(
            name='Test Masseur',
            description='Masseur desc',
            phone_number='0888888889',
            email='masseur@example.com',
            working_hours='9-18'
        )
        self.reservation_date = datetime.date(2026, 6, 5)
        self.reservation_time = datetime.time(11, 0)

    def test_duplicate_reservation_allowed_currently(self):
        # Create first reservation
        MessageReservation.objects.create(
            user=self.user,
            massage=self.massage,
            date=self.reservation_date,
            time=self.reservation_time
        )
        
        # Create second reservation for same time
        # This should currently SUCCEED because there is no validation yet
        res2 = MessageReservation.objects.create(
            user=self.user,
            massage=self.massage,
            date=self.reservation_date,
            time=self.reservation_time
        )
        self.assertEqual(MessageReservation.objects.count(), 2)

    def test_form_validation_for_duplicate_reservation(self):
        # Create first reservation
        MessageReservation.objects.create(
            user=self.user,
            massage=self.massage,
            date=self.reservation_date,
            time=self.reservation_time
        )
        
        # Try to create second reservation via form
        form_data = {
            'massage': self.massage.id,
            'date': self.reservation_date,
            'time': self.reservation_time,
            'additional_text': ''
        }
        form = ReservationCreateForm(data=form_data)
        
    def test_edit_reservation_validation(self):
        # Create first reservation
        res1 = MessageReservation.objects.create(
            user=self.user,
            massage=self.massage,
            date=self.reservation_date,
            time=self.reservation_time
        )
        
        # Try to edit it (e.g. change additional text) without changing date/time
        form_data = {
            'massage': self.massage.id,
            'date': self.reservation_date,
            'time': self.reservation_time,
            'additional_text': 'Updated text'
        }
        form = ReservationEditForm(data=form_data, instance=res1)
        self.assertTrue(form.is_valid(), form.errors)

        # Create second reservation at a different time
        other_time = datetime.time(12, 0)
        res2 = MessageReservation.objects.create(
            user=self.user,
            massage=self.massage,
            date=self.reservation_date,
            time=other_time
        )

        # Try to edit res1 to move it to res2's time
        form_data_conflict = {
            'massage': self.massage.id,
            'date': self.reservation_date,
            'time': other_time,
            'additional_text': ''
        }
        form_conflict = ReservationEditForm(data=form_data_conflict, instance=res1)
        self.assertFalse(form_conflict.is_valid())
