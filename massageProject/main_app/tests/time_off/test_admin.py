from django.contrib.admin.sites import site
from django.test import RequestFactory

from massageProject.main_app.models import TimeOff
from massageProject.main_app.tests.time_off.helpers import TimeOffTestBase, aware


class TimeOffAdminTest(TimeOffTestBase):

    def setUp(self):
        super().setUp()
        self.model_admin = site._registry[TimeOff]
        self.request = RequestFactory().post('/')
        self.request.user = self.user

    def test_registered_with_created_by_read_only(self):
        self.assertIn('created_by', self.model_admin.readonly_fields)

    def test_create_stamps_created_by(self):
        obj = TimeOff(specialist=self.specialist, start=aware(self.day, 10), end=aware(self.day, 12))
        self.model_admin.save_model(self.request, obj, form=None, change=False)
        self.assertEqual(TimeOff.objects.get().created_by, self.user)
