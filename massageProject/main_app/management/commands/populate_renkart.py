from datetime import date, time, timedelta

from django.contrib.auth import get_user_model

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from massageProject.main_app.models import (
    BusinessInfo, BusinessWorkingHours, Comment, Gallery, HomePage,
    Image, Reservation, Service, ServiceGroup, Specialist, SiteConfiguration,
    WorkingHours,
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
        services = self._populate_services(reneta_bytes)
        home_page = self._populate_home_page(logo_bytes, reneta_bytes)
        self._populate_business_working_hours(home_page)
        self._populate_comments()
        self._populate_reservations(services, specialist)

        self.stdout.write(self.style.SUCCESS("RenkArt data populated successfully!"))
        self.stdout.write(self.style.WARNING(
            "NOTE: working hours and the Art/Boudoir session price are placeholders -- "
            "confirm real values with the client before go-live."
        ))

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

    def _populate_services(self, reneta_bytes):
        groups_data = [
            ('Портретни фотосесии', 'Portrait Sessions', 0),
            ('Fine Art фотосесии', 'Fine Art Portraits', 1),
            ('Арт / Будоар фотосесии', 'Art & Concept Sessions', 2),
        ]
        groups = {}
        for name_bg, name_en, order in groups_data:
            group, _created = ServiceGroup.objects.get_or_create(
                name_bg=name_bg, defaults={'name_en': name_en, 'order': order},
            )
            groups[name_bg] = group

        services_data = [
            ('Портретни фотосесии', 'Мини фотосесия в студио', 'Mini Studio Session',
             '15 обработени снимки в студийна обстановка.',
             '15 edited photos in a studio setting.',
             'Компактна студийна фотосесия за индивидуален или семеен портрет. Включва '
             '15 обработени снимки; допълнителна снимка — 10 евро (с включен 10×15см принт).',
             'A compact studio session for an individual or family portrait. Includes 15 '
             'edited photos; an extra photo is available for €10 (includes a 10×15cm print).',
             120.00, 60, True),
            ('Портретни фотосесии', 'Мини фотосесия навън', 'Mini Outdoor Session',
             '15 обработени снимки на открито.',
             '15 edited photos outdoors.',
             'Същият мини пакет, заснет на открита локация по избор. Включва 15 обработени '
             'снимки; допълнителна снимка — 10 евро (с включен 10×15см принт).',
             'The same mini package, shot at an outdoor location of your choice. Includes '
             '15 edited photos; an extra photo is available for €10 (includes a 10×15cm print).',
             130.00, 60, False),
            ('Портретни фотосесии', 'Голям фотопакет', 'Large Photo Package',
             '35 обработени снимки + подарък 20×30см арт принт.',
             '35 edited photos + a gift 20×30cm art print.',
             'Разширена фотосесия с 35 обработени снимки и подарък — арт принт 20×30см.',
             'An extended session with 35 edited photos and a gift 20×30cm art print.',
             220.00, 90, False),
            ('Портретни фотосесии', 'Макси фотопакет', 'Maxi Photo Package',
             '50 обработени снимки + подарък 20×30см арт принт.',
             '50 edited photos + a gift 20×30cm art print.',
             'Най-пълният портретен пакет — 50 обработени снимки и подарък арт принт 20×30см.',
             'Our most complete portrait package — 50 edited photos and a gift 20×30cm art print.',
             280.00, 120, False),
            ('Fine Art фотосесии', 'Fine Art фотосесия - дете', 'Fine Art Session - Child',
             'Fine Art студийна фотосесия за дете.',
             'Fine Art studio session for a child.',
             'Студийна фотосесия на чист фон, вдъхновена от класическия портрет. Включва 10 '
             'обработени снимки + архив; допълнителна снимка — 15 евро.',
             'A studio session on a plain background, inspired by classical portrait '
             'painting. Includes 10 edited photos + archive; an extra photo is €15.',
             120.00, 90, False),
            ('Fine Art фотосесии', 'Fine Art фотосесия - индивидуална', 'Fine Art Session - Individual',
             'Fine Art портрет за тийнейджъри и възрастни.',
             'Fine Art portrait for teens and adults.',
             'Индивидуален Fine Art портрет на чист фон. Включва 10 обработени снимки + '
             'архив; допълнителна снимка — 15 евро.',
             'An individual Fine Art portrait on a plain background. Includes 10 edited '
             'photos + archive; an extra photo is €15.',
             140.00, 90, True),
            ('Fine Art фотосесии', 'Fine Art фотосесия - двойка', 'Fine Art Session - Couple',
             'Fine Art портрет за двойки.',
             'Fine Art portrait for couples.',
             'Fine Art фотосесия за двама на чист фон. Включва 10 обработени снимки + '
             'архив; допълнителна снимка — 15 евро.',
             'A Fine Art session for two on a plain background. Includes 10 edited photos '
             '+ archive; an extra photo is €15.',
             160.00, 90, False),
            ('Fine Art фотосесии', 'Fine Art фотосесия - семейство', 'Fine Art Session - Family',
             'Fine Art портрет за цялото семейство.',
             'Fine Art portrait for the whole family.',
             'Fine Art фамилен портрет на чист фон. Включва 10 обработени снимки + архив; '
             'допълнителна снимка — 15 евро.',
             'A Fine Art family portrait on a plain background. Includes 10 edited photos '
             '+ archive; an extra photo is €15.',
             180.00, 90, False),
            ('Fine Art фотосесии', 'Fine Art макси пакет', 'Fine Art Maxi Package',
             '30 обработени снимки + подарък 20×30см арт принт.',
             '30 edited photos + a gift 20×30cm art print.',
             'Разширеният Fine Art пакет — 30 обработени снимки и подарък арт принт 20×30см.',
             'The extended Fine Art package — 30 edited photos and a gift 20×30cm art print.',
             280.00, 90, False),
            ('Арт / Будоар фотосесии', 'Арт / Будоар фотосесия', 'Art & Concept Session',
             'Индивидуален концептуален проект — цена по договаряне.',
             'A fully custom concept shoot — price by arrangement.',
             'Напълно индивидуална арт фотосесия с избран от Вас концепт, гардероб, '
             'аксесоари и локация. Продължителност 2–8 часа според концепцията. '
             'Посочената цена е начална — точната цена се договаря индивидуално според '
             'обхвата на проекта.',
             'A fully custom art photo session with your chosen concept, wardrobe, props, '
             'and location. Duration is 2–8 hours depending on the concept. The listed '
             "price is a starting point — the final price is agreed individually based on "
             "the project's scope.",
             150.00, 180, True),
        ]

        services = []
        for (group_name, name_bg, name_en, short_bg, short_en, desc_bg, desc_en,
             price, duration, home_page) in services_data:
            service, created = Service.objects.get_or_create(
                name_bg=name_bg,
                defaults={
                    'name_en': name_en,
                    'short_description_bg': short_bg,
                    'short_description_en': short_en,
                    'description_bg': desc_bg,
                    'description_en': desc_en,
                    'price': price,
                    'duration_in_minutes': duration,
                    'home_page': home_page,
                    'group': groups[group_name],
                }
            )
            if created:
                service.image.save('reneta.jpg', ContentFile(reneta_bytes), save=True)
                self.stdout.write(f"Created service: {service.name}")
            services.append(service)
        return services

    def _populate_home_page(self, logo_bytes, reneta_bytes):
        home_page = HomePage.objects.filter(pk=1).first()
        if home_page is None:
            gallery = Gallery.objects.create(
                gallery_type=Gallery.TYPE_HOMEPAGE, title_bg='RenkArt', title_en='RenkArt',
            )
            home_page = HomePage.objects.create(
                pk=1,
                brand_name_bg='RenkArt — Портретна и Арт Фотография',
                brand_name_en='RenkArt — Portrait & Art Photography',
                description_bg=(
                    'Добре дошли в RenkArt — където всеки кадър разказва история. '
                    'Портретна и арт фотография, вдъхновена от класическата живопис и '
                    'съвременния разказ.'
                ),
                description_en=(
                    'Welcome to RenkArt — where every frame tells a story. Portrait and '
                    'art photography inspired by classical painting and modern storytelling.'
                ),
                footer_tagline_bg='Портретна и арт фотография в Стара Загора.',
                footer_tagline_en='Portrait and art photography in Stara Zagora.',
                gallery=gallery,
            )
            home_page.logo.save('logo33.jpg', ContentFile(logo_bytes), save=True)
            self.stdout.write(f"Created home page: {home_page.brand_name}")

        if not home_page.gallery.images.exists():
            image = Image.objects.create(
                gallery=home_page.gallery,
                alt_text_bg='Ренета Кирилова с фотоапарат',
                alt_text_en='Reneta Kirilova with a camera',
            )
            image.image.save('reneta.jpg', ContentFile(reneta_bytes), save=True)
            self.stdout.write("Added hero image to gallery")

        return home_page

    def _populate_business_working_hours(self, home_page):
        rows = [
            ('Вторник – Събота', 'Tuesday – Saturday', '10:00 - 18:00', '10:00 - 18:00', 0),
            ('Неделя, Понеделник', 'Sunday, Monday', '', '', 1),
        ]
        for day_label_bg, day_label_en, hours_bg, hours_en, order in rows:
            BusinessWorkingHours.objects.get_or_create(
                home_page=home_page, day_label_bg=day_label_bg,
                defaults={
                    'day_label_en': day_label_en,
                    'hours_bg': hours_bg,
                    'hours_en': hours_en,
                    'order': order,
                },
            )
        self.stdout.write(
            "Set placeholder business hours display -- confirm real hours with the client"
        )

    def _populate_comments(self):
        comments_data = [
            ('Виктория Н.',
             'Фотосесията с Ренета беше невероятно преживяване! Снимките са живи, '
             'топли и много артистични.', 5),
            ('Стоян П.',
             'Професионално отношение и страхотен резултат. Препоръчвам Fine Art '
             'пакета на всеки, който търси нещо различно.', 5),
            ('Мария Д.',
             'Много благодаря за търпението по време на семейната ни фотосесия! '
             'Децата се почувстваха напълно спокойно.', 5),
            ('Георги К.',
             'Артистичната фотосесия надмина очакванията ми — истинско произведение '
             'на изкуството.', 5),
            ('Ивелина Т.',
             'Атмосферата в студиото е уютна, а Ренета има невероятно око за детайла.', 4),
        ]
        for author, content, rating in comments_data:
            comment, created = Comment.objects.get_or_create(
                author=author, content=content,
                defaults={'rating': rating, 'is_reviewed': True},
            )
            if created:
                self.stdout.write(f"Created comment by {author}")

    def _populate_reservations(self, services, specialist):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            phone_number='0888920099',
            defaults={
                'email': 'demo.client@example.com',
                'first_name': 'Виктория',
                'last_name': 'Николова',
            }
        )
        if created:
            user.set_password('1234')
            user.save()

        services_by_name = {s.name: s for s in services}
        mini_studio = services_by_name['Мини фотосесия в студио']
        fine_art_couple = services_by_name['Fine Art фотосесия - двойка']
        fine_art_individual = services_by_name['Fine Art фотосесия - индивидуална']
        large_package = services_by_name['Голям фотопакет']

        today = date.today()

        def next_open_day(d):
            # Reneta is closed Sunday (6) and Monday (0)
            while d.weekday() in (0, 6):
                d += timedelta(days=1)
            return d

        reservations_data = [
            (mini_studio, today - timedelta(days=5), time(11, 0), True),
            (fine_art_couple, today - timedelta(days=2), time(14, 0), True),
            (fine_art_individual, next_open_day(today + timedelta(days=2)), time(10, 0), False),
            (large_package, next_open_day(today + timedelta(days=7)), time(15, 0), False),
        ]
        for service, d, t, is_past in reservations_data:
            defaults = {'specialist': specialist, 'additional_text': 'Очакваме сесията с нетърпение.'}
            if is_past:
                defaults['status'] = Reservation.STATUS_COMPLETED
            reservation, created = Reservation.objects.get_or_create(
                service=service, user=user, date=d, time=t, defaults=defaults,
            )
            if created:
                self.stdout.write(f"Created reservation for {service.name} on {d}")
