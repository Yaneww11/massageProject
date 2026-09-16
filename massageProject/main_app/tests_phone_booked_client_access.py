from django.contrib import admin
from django.test import TestCase
from django.urls import reverse

from massageProject.main_app.models import BusinessInfo


class BusinessInfoPhoneRequiredTest(TestCase):
    def test_admin_form_rejects_empty_phone(self):
        form_class = admin.site._registry[BusinessInfo].get_form(None)
        self.assertIn('phone', form_class.base_fields)
        form = form_class(data={'phone': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)


class AuthEntryNoteTest(TestCase):
    def setUp(self):
        BusinessInfo.objects.create(description="Test Studio", phone="0888123456")

    def test_note_passed_to_modal_with_phone(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'телефонния номер, с който сте ги направили')
        self.assertContains(response, '0888123456')

    def test_note_element_present_and_hidden_by_default(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'id="auth-modal-note"')
