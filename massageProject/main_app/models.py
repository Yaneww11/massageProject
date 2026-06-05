from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta

class Massage(models.Model):
    name = models.CharField(max_length=80)
    description = models.TextField()
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    duration_in_minutes = models.IntegerField()
    short_description = models.CharField(max_length=255)
    image = models.ImageField(upload_to='massages/')
    home_page = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class Masseur(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to='masseurs/')
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()

    def __str__(self):
        return self.name

class WorkingHours(models.Model):
    DAYS_OF_WEEK = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]
    masseur = models.ForeignKey(Masseur, on_delete=models.CASCADE, related_name='working_hours')
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = ('masseur', 'day_of_week')

class MessageStudio(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    main_image = models.ImageField(upload_to='studios/')
    address = models.CharField(max_length=255)

class MessageReservation(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_COMPLETED = 'completed'
    STATUS_NOSHOW = 'no_show'
    STATUS_DELETED = 'deleted'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Предстояща'),
        (STATUS_COMPLETED, 'Завършена'),
        (STATUS_NOSHOW, 'Не се е явил'),
        (STATUS_DELETED, 'Отказана'),
    ]

    massage = models.ForeignKey(
        Massage,
        on_delete=models.CASCADE,
        related_name='reservations'
    )

    masseur = models.ForeignKey(
        Masseur,
        on_delete=models.CASCADE,
        related_name='reservations'
    )

    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='reservations'
    )

    time = models.TimeField()
    date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE
    )
    updated_at = models.DateTimeField(auto_now=True)
    status_updated_at = models.DateTimeField(null=True, blank=True)
    status_updated_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='status_updates'
    )
    additional_text = models.TextField(default='', blank=True)

    # Custom Managers
    class ReservationQuerySet(models.QuerySet):
        def active(self):
            return self.filter(status='active')
        def past(self):
            return self.filter(status__in=['completed', 'no_show'])
        def deleted(self):
            return self.filter(status='deleted')

    class ReservationManager(models.Manager):
        def get_queryset(self):
            return MessageReservation.ReservationQuerySet(self.model, using=self._db).exclude(status='deleted')
        def active(self):
            return self.get_queryset().active()
        def past(self):
            return self.get_queryset().past()

    objects = ReservationManager()
    all_objects = models.Manager()

    def clean(self):
        # Use _id to avoid RelatedObjectDoesNotExist if the field is not set
        if not all([self.massage_id, self.masseur_id, self.date, self.time]):
            return

        # 0. Only validate Active reservations for overlaps
        if self.status != self.STATUS_ACTIVE:
            return

        # 1. Lead time check (2 hours)
        reservation_datetime = timezone.make_aware(datetime.combine(self.date, self.time))
        if reservation_datetime < timezone.now() + timedelta(hours=2):
            raise ValidationError("Резервация трябва да се направи поне 2 часа предварително.")

        # 2. Working hours check
        day = self.date.weekday()
        hours = self.masseur.working_hours.filter(day_of_week=day).first()
        if not hours:
            raise ValidationError(f"{self.masseur.name} не работи в този ден.")
        
        duration = timedelta(minutes=self.massage.duration_in_minutes)
        end_time = (datetime.combine(self.date, self.time) + duration).time()

        if self.time < hours.start_time or end_time > hours.end_time:
            raise ValidationError(f"Избраният час е извън работното време на {self.masseur.name} ({hours.start_time} - {hours.end_time}).")

        # 3. Overlap check
        existing_reservations = MessageReservation.objects.filter(
            masseur=self.masseur,
            date=self.date,
            status=self.STATUS_ACTIVE
        ).exclude(pk=self.pk)

        for res in existing_reservations:
            res_duration = timedelta(minutes=res.massage.duration_in_minutes)
            res_end = (datetime.combine(res.date, res.time) + res_duration).time()
            
            # (StartA < EndB) and (EndA > StartB)
            if self.time < res_end and end_time > res.time:
                raise ValidationError(f"Часът се застъпва с друга резервация за {self.masseur.name}.")

    def change_status(self, new_status, user=None):
        self.status = new_status
        self.status_updated_at = timezone.now()
        if user:
            self.status_updated_by = user
        self.save()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class Gallery(models.Model):
    images = models.ManyToManyField('Image', related_name='galleries', through='GalleryImage')

class Image(models.Model):
    image = models.ImageField(upload_to='studios/gallery/')
    alt_text = models.CharField(max_length=255)

    def __str__(self):
        return self.alt_text

class GalleryImage(models.Model):
    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE)
    image = models.ForeignKey(Image, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('gallery', 'image')

class HomePage(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    gallery = models.OneToOneField(
        Gallery,
        on_delete=models.CASCADE,
        related_name='home_page'
    )
    privacy_policy_content = models.TextField(null=True, blank=True)

class Comment(models.Model):
    author = models.CharField(
        max_length=30,
    )

    content = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    is_reviewed = models.BooleanField(
        default=False,
    )



