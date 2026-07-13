from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


class DateOfBirthFieldTest(TestCase):
    def test_user_can_be_created_without_date_of_birth(self):
        user = User.objects.create_user(
            email='nodob@example.com', phone_number='0888700001', password='pass1234',
        )
        self.assertIsNone(user.date_of_birth)

    def test_user_can_store_a_date_of_birth(self):
        user = User.objects.create_user(
            email='withdob@example.com', phone_number='0888700002', password='pass1234',
        )
        user.date_of_birth = '1990-05-20'
        user.save(update_fields=['date_of_birth'])
        user.refresh_from_db()
        self.assertEqual(str(user.date_of_birth), '1990-05-20')
