from datetime import time


from massageProject.accounts.models import CustomUser
from massageProject.main_app.models import Service, Specialist, WorkingHours


class ReservationAuditFixTestBase:
    def _make_base_objects(self):
        self.user = CustomUser.objects.create_user(
            phone_number='0888888888',
            email='test@example.com',
            password='password123',
            first_name='John',
            last_name='Doe',
        )
        self.service = Service.objects.create(
            name='Relax Service',
            description='desc',
            price=50.00,
            duration_in_minutes=60,
            short_description='short',
        )
        self.specialist = Specialist.objects.create(
            name='John Doe',
            description='expert',
            phone_number='0888888889',
            email='john@example.com',
        )
        for i in range(7):
            WorkingHours.objects.create(
                specialist=self.specialist,
                day_of_week=i,
                start_time=time(9, 0),
                end_time=time(17, 0),
            )
