from django import forms
from massageProject.main_app.models import MessageReservation


class ReservationForm(forms.ModelForm):
    class Meta:
        model = MessageReservation
        fields = ['massage','date', 'time', 'additional_text']