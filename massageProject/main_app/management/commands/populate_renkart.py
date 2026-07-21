from datetime import time

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from massageProject.main_app.models import (
    BusinessInfo, Specialist, SiteConfiguration, WorkingHours,
)

LOGO_URL = 'https://renkart.net/images/logo33.jpg'
RENETA_URL = 'https://renkart.net/images/reneta.jpg'


class Command(BaseCommand):
    help = 'Populate a database with real RenkArt (photography studio) content'

    def handle(self, *args, **options):
        self.stdout.write("Populating RenkArt data...")

        logo_bytes = self._fetch_image(LOGO_URL)
        reneta_bytes = self._fetch_image(RENETA_URL)

        self._populate_site_configuration()
        self._populate_business_info(reneta_bytes)
        specialist = self._populate_specialist(reneta_bytes)
        self._populate_working_hours(specialist)

        self.stdout.write(self.style.SUCCESS("RenkArt core data populated successfully!"))

    def _fetch_image(self, url):
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            raise CommandError(f"Could not download {url}: HTTP {response.status_code}")
        return response.content

    def _populate_site_configuration(self):
        config = SiteConfiguration.get_solo()
        config.primary_color = '#1A1A1A'
        config.primary_light_color = '#2E2E2E'
        config.secondary_color = '#EDE7DD'
        config.accent_color = '#B08D57'
        config.background_color = '#FAF8F5'
        config.text_color = '#1A1A1A'
        config.text_muted_color = '#6B6259'
        config.font_pair = 'playfair_montserrat'
        config.style_preset = 'soft'
        config.hero_variant = 'fullbleed'
        config.service_singular_bg = 'фотосесия'
        config.service_singular_en = 'photo session'
        config.service_plural_bg = 'фотосесии'
        config.service_plural_en = 'photo sessions'
        config.specialist_singular_bg = 'фотограф'
        config.specialist_singular_en = 'photographer'
        config.specialist_plural_bg = 'фотографи'
        config.specialist_plural_en = 'photographers'
        config.booking_enabled = True
        config.comments_enabled = True
        config.google_login_enabled = True
        config.save()
        self.stdout.write("Configured RenkArt theme, terminology, and feature flags")

    def _populate_business_info(self, reneta_bytes):
        business_info, created = BusinessInfo.objects.get_or_create(
            name_bg='RenkArt',
            defaults={
                'name_en': 'RenkArt',
                'description_bg': (
                    'RenkArt е студио за портретна и арт фотография в Стара Загора, '
                    'основано от Ренета Кирилова. Специализираме се в мини и големи '
                    'фотопакети, Fine Art портрети и напълно индивидуални арт/будоар '
                    'концепции.'
                ),
                'description_en': (
                    'RenkArt is a portrait and art photography studio in Stara Zagora, '
                    'founded by Reneta Kirilova. We specialize in mini and large photo '
                    'packages, Fine Art portraits, and fully custom art/concept sessions.'
                ),
                'address_bg': 'гр. Стара Загора, ул. "Орфей" 3 (до Музикалното училище)',
                'address_en': 'Stara Zagora, 3 Orpheus St. (near the Music School)',
                'phone': '0896710264',
                'email_address': 'art76@abv.bg',
                'facebook_link': 'https://www.facebook.com/RenkArt',
            }
        )
        if created:
            business_info.main_image.save('reneta.jpg', ContentFile(reneta_bytes), save=True)
            self.stdout.write(f"Created business info: {business_info.name}")
        return business_info

    def _populate_specialist(self, reneta_bytes):
        specialist, created = Specialist.objects.get_or_create(
            name_bg='Ренета Кирилова',
            defaults={
                'name_en': 'Reneta Kirilova',
                'description_bg': (
                    "Ренета Кирилова (позната на приятелите като 'Рени') е портретен и "
                    'арт фотограф от Стара Загора. Завършила е изобразително изкуство, '
                    'седем години е преподавала визуални изкуства, а от престоя си в '
                    'Италия (2008–2012 г.) се посвещава сериозно на фотографията. Работи '
                    'предимно в черно-бяло и цвят, търси разказваща, емоционална '
                    'композиция и често снима в диптих, включително автопортрети.'
                ),
                'description_en': (
                    "Reneta Kirilova ('Reni' to friends) is a portrait and fine-art "
                    'photographer based in Stara Zagora, Bulgaria. She studied fine arts, '
                    'taught visual arts for seven years, and turned seriously to '
                    'photography during her time in Italy (2008–2012). She favors '
                    'black-and-white and color portrait work, story-driven and emotive '
                    'compositions, and often works in diptych form, including '
                    'self-portraits.'
                ),
                'phone_number': '0896710264',
                'email': 'art76@abv.bg',
            }
        )
        if created:
            specialist.image.save('reneta.jpg', ContentFile(reneta_bytes), save=True)
            self.stdout.write(f"Created specialist: {specialist.name}")
        return specialist

    def _populate_working_hours(self, specialist):
        for day in (1, 2, 3, 4, 5):  # Tue-Sat; closed Sun (6) and Mon (0)
            WorkingHours.objects.get_or_create(
                specialist=specialist, day_of_week=day,
                defaults={'start_time': time(10, 0), 'end_time': time(18, 0)},
            )
        self.stdout.write(
            "Set placeholder working hours (Tue-Sat 10:00-18:00) -- "
            "confirm real hours with the client"
        )
