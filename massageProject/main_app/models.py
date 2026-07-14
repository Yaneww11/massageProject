from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db.models import JSONField
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import datetime, timedelta

class ServiceGroup(models.Model):
    name = models.CharField(max_length=100, verbose_name=_('Наименование'))
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_('Ред'))

    class Meta:
        ordering = ['order']
        verbose_name = _('Група услуги')
        verbose_name_plural = _('Групи услуги')

    def __str__(self):
        return self.name


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
    group = models.ForeignKey(
        'ServiceGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='massages',
        verbose_name=_('Група'),
    )

    class Meta:
        verbose_name = _('Масаж')
        verbose_name_plural = _('Масажи')

    def clean(self):
        if self.home_page:
            qs = Massage.objects.filter(home_page=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.count() >= 3:
                raise ValidationError({
                    'home_page': _('Можете да изберете най-много 3 предпочитани масажа.')
                })

    def __str__(self):
        return self.name

class Masseur(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to='masseurs/')
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()

    class Meta:
        verbose_name = _('Терапевт')
        verbose_name_plural = _('Терапевти')

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
        verbose_name = _('Работно време')
        verbose_name_plural = _('Работно време')

    def __str__(self):
        return f"{self.masseur.name} - {self.get_day_of_week_display()}"

class MessageStudio(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    main_image = models.ImageField(upload_to='studios/')
    address = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True)
    email_address = models.EmailField()
    facebook_link = models.URLField(null=True, blank=True)
    instagram_link = models.URLField(null=True, blank=True)
    tik_tok_link = models.URLField(null=True, blank=True)

    class Meta:
        verbose_name = _('Студио')
        verbose_name_plural = _('Студиа')

    def __str__(self):
        return self.name

class MessageReservation(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_COMPLETED = 'completed'
    STATUS_NOSHOW = 'no_show'
    STATUS_DELETED = 'deleted'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, _('Предстояща')),
        (STATUS_COMPLETED, _('Завършена')),
        (STATUS_NOSHOW, _('Не се е явил')),
        (STATUS_DELETED, _('Отказана')),
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
    additional_text = models.TextField(default='', blank=True, max_length=500, validators=[MaxLengthValidator(500)])

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

    @property
    def end_time(self):
        start_dt = datetime.combine(self.date, self.time)
        duration = timedelta(minutes=self.massage.duration_in_minutes)
        return (start_dt + duration).time()

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
            raise ValidationError(_("Резервация трябва да се направи поне 2 часа предварително."))

        # 2. Working hours check
        day = self.date.weekday()
        hours = self.masseur.working_hours.filter(day_of_week=day).first()
        if not hours:
            raise ValidationError(_("%(name)s не работи в този ден.") % {'name': self.masseur.name})

        duration = timedelta(minutes=self.massage.duration_in_minutes)
        end_time = (datetime.combine(self.date, self.time) + duration).time()

        if self.time < hours.start_time or end_time > hours.end_time:
            raise ValidationError(
                _("Избраният час е извън работното време на %(name)s (%(start)s - %(end)s).") % {
                    'name': self.masseur.name,
                    'start': hours.start_time,
                    'end': hours.end_time,
                }
            )

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
                raise ValidationError(
                    _("Часът се застъпва с друга резервация за %(name)s.") % {'name': self.masseur.name}
                )

    def change_status(self, new_status, user=None):
        self.status = new_status
        self.status_updated_at = timezone.now()
        if user:
            self.status_updated_by = user
        self.save()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('Резервация')
        verbose_name_plural = _('Резервации')

    def __str__(self):
        return f"{self.massage.name} - {self.date} {self.time.strftime('%H:%M')}"

class Gallery(models.Model):
    images = models.ManyToManyField('Image', related_name='galleries', through='GalleryImage')
    title = models.CharField(max_length=255, blank=True, verbose_name=_('Заглавие'))
    short_description = models.TextField(blank=True, verbose_name=_('Кратко описание'))

    class Meta:
        verbose_name = _('Галерия')
        verbose_name_plural = _('Галерии')

    def __str__(self):
        if hasattr(self, 'home_page'):
            return f"{_('Галерия')} - {self.home_page.brand_name}"
        return self.title or f"{_('Галерия')} {self.id}"

class Image(models.Model):
    image = models.ImageField(upload_to='studios/gallery/')
    alt_text = models.CharField(max_length=255)

    class Meta:
        verbose_name = _('Изображение')
        verbose_name_plural = _('Изображения')

    def __str__(self):
        return self.alt_text

class GalleryImage(models.Model):
    gallery = models.ForeignKey(Gallery, on_delete=models.CASCADE)
    image = models.ForeignKey(Image, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('gallery', 'image')
        verbose_name = _('Изображение в галерия')
        verbose_name_plural = _('Изображения в галерия')

    def __str__(self):
        return f"{self.gallery} - {self.image.alt_text}"


class GalleryAlbum(models.Model):
    title = models.CharField(max_length=255, verbose_name=_('Заглавие'))
    description = models.TextField(blank=True, verbose_name=_('Описание'))
    slug = models.SlugField(unique=True, verbose_name=_('Slug'))
    order = models.PositiveIntegerField(default=0, verbose_name=_('Ред'))

    class Meta:
        ordering = ['order']
        verbose_name = _('Албум')
        verbose_name_plural = _('Албуми')

    def __str__(self):
        return self.title

    @property
    def cover(self):
        return self.photos.order_by('order').first()

    @property
    def photo_count(self):
        return self.photos.count()


class AlbumPhoto(models.Model):
    album = models.ForeignKey(GalleryAlbum, on_delete=models.CASCADE, related_name='photos', verbose_name=_('Албум'))
    image = models.ImageField(upload_to='gallery/albums/', verbose_name=_('Изображение'))
    alt_text = models.CharField(max_length=255, blank=True, verbose_name=_('Алт текст'))
    order = models.PositiveIntegerField(default=0, verbose_name=_('Ред'))

    class Meta:
        ordering = ['order']
        verbose_name = _('Снимка в албум')
        verbose_name_plural = _('Снимки в албум')

    def __str__(self):
        return self.alt_text or f"Снимка {self.order}"


class HomePage(models.Model):
    brand_name = models.CharField(max_length=255)
    description = models.TextField()
    logo = models.ImageField(upload_to='branding/', null=True, blank=True)
    gallery = models.OneToOneField(
        Gallery,
        on_delete=models.CASCADE,
        related_name='home_page'
    )
    privacy_policy_content = models.TextField(null=True, blank=True)
    footer_tagline = models.TextField(blank=True)

    class Meta:
        verbose_name = _('Начална страница')
        verbose_name_plural = _('Начални страници')

    def save(self, *args, **kwargs):
        if not self.pk and HomePage.objects.exists():
            return
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'brand_name': 'Relax & Health',
                'description': 'Welcome to our studio.',
                'gallery': Gallery.objects.create(),
            }
        )
        return obj

    def __str__(self):
        return self.brand_name


class StudioWorkingHours(models.Model):
    home_page = models.ForeignKey(
        HomePage,
        on_delete=models.CASCADE,
        related_name='studio_working_hours',
    )
    day_label = models.CharField(
        max_length=100,
        verbose_name=_('Ден / период'),
        help_text=_('напр. "Понеделник до Петък"'),
    )
    hours = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Часове'),
        help_text=_('напр. "9:00 - 18:00" — оставете празно за "Почивен ден"'),
    )
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_('Ред'))

    class Meta:
        ordering = ['order']
        verbose_name = _('Работно време на студиото')
        verbose_name_plural = _('Работно време на студиото')

    def __str__(self):
        return f"{self.day_label}: {self.hours or _('Почивен ден')}"


class Comment(models.Model):
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    reservation = models.ForeignKey(
        'MessageReservation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='comments',
        verbose_name=_('резервация'),
    )

    author = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    content = models.TextField(max_length=2000, validators=[MaxLengthValidator(2000)])

    rating = models.IntegerField(default=5)

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    is_reviewed = models.BooleanField(
        default=False,
    )

    class Meta:
        verbose_name = _('Коментар')
        verbose_name_plural = _('Коментари')

    def __str__(self):
        return f"{self.display_name} - {self.created_at.strftime('%d.%m.%Y')}"

    @property
    def display_name(self):
        if self.author:
            return self.author
        if self.user_id:
            return self.user.get_full_name() or str(self.user.phone_number)
        return 'Клиент'



