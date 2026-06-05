import os
from datetime import date, time, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from massageProject.main_app.models import (
    Massage, Masseur, MessageStudio, HomePage, Gallery, Image, GalleryImage,
    MessageReservation, Comment
)
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate database with realistic data'

    def handle(self, *args, **options):
        self.stdout.write("Populating database...")

        # 1. Create Basic User
        user, created = User.objects.get_or_create(
            phone_number='0888888888',
            defaults={
                'email': 'user@example.com',
                'first_name': 'Georgi',
                'last_name': 'Georgiev',
            }
        )
        if created:
            user.set_password('1234')
            user.save()
            self.stdout.write(f"Created basic user: {user.phone_number}")
        else:
             # Ensure password is set to 1234 even if user existed
            user.set_password('1234')
            user.save()

        # 2. Create Masseurs
        masseurs_data = [
            ('Ivan Ivanov', 'ivan@example.com', '0891111111'),
            ('Maria Petrova', 'maria@example.com', '0892222222'),
            ('Elena Boneva', 'elena@example.com', '0893333333'),
        ]
        masseurs = []
        for name, email, phone in masseurs_data:
            masseur, created = Masseur.objects.get_or_create(
                name=name,
                defaults={
                    'description': f'Expert in various massage techniques with years of experience. Part of the Tranquil Oasis team.',
                    'image': 'masseurs/measure.jpg',
                    'email': email,
                    'phone_number': phone,
                }
            )
            masseurs.append(masseur)
            if created:
                # Add some working hours for each masseur (Mon-Fri 9-18, Sat 10-16)
                from massageProject.main_app.models import WorkingHours
                for day in range(5): # Mon-Fri
                    WorkingHours.objects.get_or_create(
                        masseur=masseur,
                        day_of_week=day,
                        defaults={'start_time': time(9, 0), 'end_time': time(18, 0)}
                    )
                WorkingHours.objects.get_or_create(
                    masseur=masseur,
                    day_of_week=5, # Sat
                    defaults={'start_time': time(10, 0), 'end_time': time(16, 0)}
                )
                self.stdout.write(f"Created masseur and working hours for: {name}")

        # 3. Create Massages
        massages_data = [
            ('Swedish Massage', 'A gentle full-body massage that is great for people who are new to massage, have a lot of tension, or are sensitive to touch.', 60.00, 60, True),
            ('Deep Tissue Massage', 'Uses more pressure than a Swedish massage. It is a good option if you have muscle problems, such as soreness, injury, or imbalance.', 90.00, 90, True),
            ('Aromatherapy Massage', 'Best for people who want to have an emotional healing component to their massage. It can help boost your mood and reduce stress.', 70.00, 60, True),
            ('Hot Stone Massage', 'Best for people who have muscle pain and tension or who simply want to relax. It is similar to a Swedish massage, but the therapist uses heated stones.', 85.00, 75, False),
            ('Sports Massage', 'A good option if you have a repetitive use injury to a muscle, such as what you may get from playing a sport.', 65.00, 60, False),
            ('Reflexology', 'Uses gentle to firm pressure on different pressure points of the feet, hands, and ears. It is best for people who are looking to relax or restore their energy levels.', 50.00, 45, False),
        ]
        massages = []
        for name, desc, price, duration, home in massages_data:
            massage, created = Massage.objects.get_or_create(
                name=name,
                defaults={
                    'description': desc,
                    'short_description': desc[:250],
                    'price': price,
                    'duration_in_minutes': duration,
                    'image': 'massages/massage-1.jpg',
                    'home_page': home
                }
            )
            massages.append(massage)
            if created:
                self.stdout.write(f"Created massage: {name}")

        # 4. Create MessageStudio
        studio, created = MessageStudio.objects.get_or_create(
            name='Tranquil Oasis Studio',
            defaults={
                'description': 'A sanctuary of peace and relaxation. Our studio offers a wide range of therapeutic massages in a tranquil environment.',
                'main_image': 'studios/massage_studio.jpg',
                'address': 'ul. "Tsar Ivan Asen II" 12, 1124 Sofia, Bulgaria'
            }
        )
        if created:
            self.stdout.write(f"Created studio: {studio.name}")

        # 5. Create Gallery and Home Page
        gallery, created = Gallery.objects.get_or_create()
        if created:
            # Create some images for the gallery
            for i in range(3):
                img = Image.objects.create(
                    image='studios/gallery/massage_studio.jpg',
                    alt_text=f'Studio Interior {i+1}'
                )
                GalleryImage.objects.create(gallery=gallery, image=img)
            self.stdout.write("Created gallery with 3 images")
        elif not gallery.images.exists():
             for i in range(3):
                img = Image.objects.create(
                    image='studios/gallery/massage_studio.jpg',
                    alt_text=f'Studio Interior {i+1}'
                )
                GalleryImage.objects.create(gallery=gallery, image=img)
             self.stdout.write("Added images to existing empty gallery")

        home_page, created = HomePage.objects.get_or_create(
            title='Tranquil Oasis - Your Path to Relaxation',
            defaults={
                'description': 'Welcome to Tranquil Oasis, where we believe in the healing power of touch. Escape the city stress and rejuvenate your body and mind.',
                'gallery': gallery
            }
        )
        if created:
            self.stdout.write(f"Created home page: {home_page.title}")

        # 6. Create Reservations
        today = date.today()
        reservations_data = [
            (massages[0], masseurs[0], today - timedelta(days=5), time(10, 0)),
            (massages[1], masseurs[1], today - timedelta(days=1), time(14, 0)),
            (massages[2], masseurs[0], today + timedelta(days=2), time(11, 0)),
            (massages[3], masseurs[2], today + timedelta(days=7), time(16, 0)),
        ]
        for msg, msr, d, t in reservations_data:
            res, created = MessageReservation.objects.get_or_create(
                massage=msg,
                user=user,
                date=d,
                time=t,
                defaults={
                    'masseur': msr,
                    'additional_text': 'Looking forward to the session.'
                }
            )
            if created:
                self.stdout.write(f"Created reservation for {msg.name} on {d}")

        # 7. Create Comments
        if Comment.objects.count() < 5:
            comments_data = [
                ('Stoyan', 'Wonderful experience! Very professional staff.'),
                ('Mariya', 'The Swedish massage was so relaxing. I highly recommend this studio.'),
                ('Petar', 'Great atmosphere and skilled masseurs.'),
                ('Ana', 'Truly a tranquil oasis in the heart of the city.'),
                ('Dimitar', 'Deep tissue massage helped me with my back pain. Excellent service.'),
            ]
            for author, content in comments_data:
                Comment.objects.create(author=author, content=content)
                self.stdout.write(f"Created comment by {author}")

        self.stdout.write(self.style.SUCCESS("Database populated successfully!"))
