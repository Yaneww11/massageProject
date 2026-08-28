import os
from io import BytesIO

from PIL import Image as PILImage, ImageOps
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MinValueValidator, RegexValidator
from django.db.models import JSONField
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from datetime import datetime, timedelta

from massageProject.main_app.theme import COLOR_PRESETS

class ServiceGroup(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name=_('Наименование'),
        help_text=_('Показва се като таб-категория на страницата с услуги.'),
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_('Ред'),
        help_text=_('Определя реда, в който категориите се показват на страницата с услуги.'),
    )

    class Meta:
        ordering = ['order']
        verbose_name = _('Група услуги')
        verbose_name_plural = _('Групи услуги')

    def __str__(self):
        return self.name


class Service(models.Model):
    name = models.CharField(
        max_length=80,
        help_text=_(
            'Показва се в предпочитаните услуги на началната страница, на страницата с '
            'услуги и навсякъде в процеса на резервация.'
        ),
    )
    description = models.TextField(
        help_text=_(
            'Показва се разгънат (при клик "Научете повече" / върху картата) в '
            'предпочитаните услуги на началната страница.'
        ),
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_(
            'Показва се на страницата с услуги и в предпочитаните услуги на '
            'началната страница.'
        ),
    )
    duration_in_minutes = models.IntegerField(
        help_text=_(
            'Показва се на страницата с услуги и в предпочитаните услуги на '
            'началната страница; използва се и за изчисляване на '
            'свободните часове за резервация.'
        ),
    )
    short_description = models.CharField(
        max_length=255,
        help_text=_(
            'Кратък текст, показван в предпочитаните услуги на началната страница и '
            'във всяка карта на страницата с услуги.'
        ),
    )
    image = models.ImageField(
        upload_to='services/',
        help_text=_(
            'Показва се на картата в страницата с услуги и в предпочитаните услуги на '
            'началната страница. Ако е празно, се '
            'показва градиентен placeholder.'
        ),
        blank=True,
        null=True,
    )
    home_page = models.BooleanField(
        default=False,
        help_text=_(
            'Когато е отметнато, услугата се показва в секция "Предпочитани услуги" на '
            'началната страница (максимум 3).'
        ),
    )
    group = models.ForeignKey(
        'ServiceGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='services',
        verbose_name=_('Група'),
        help_text=_('Определя под кой таб-категория е класирана услугата на страницата с услуги.'),
    )

    class Meta:
        verbose_name = _('Масаж')
        verbose_name_plural = _('Масажи')

    def clean(self):
        if self.home_page:
            qs = Service.objects.filter(home_page=True)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.count() >= 3:
                raise ValidationError({
                    'home_page': _('Можете да изберете най-много 3 предпочитани масажа.')
                })

    def __str__(self):
        return self.name

class Specialist(models.Model):
    name = models.CharField(
        max_length=255,
        help_text=_(
            'Показва се в селектора на терапевти на страницата за резервация и в '
            'профила на клиента (предстоящи/минали резервации).'
        ),
    )
    description = models.TextField(
        help_text=_('Показва се като кратко био в селектора на терапевти на страницата за резервация.'),
    )
    image = models.ImageField(upload_to='specialists/')
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    user = models.OneToOneField(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='specialist_profile',
    )

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
    specialist = models.ForeignKey(Specialist, on_delete=models.CASCADE, related_name='working_hours')
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK)
    start_time = models.TimeField(
        help_text=_(
            'Не се показва директно, но определя кои часове се предлагат на клиентите при '
            'резервация с този терапевт в този ден.'
        ),
    )
    end_time = models.TimeField(
        help_text=_(
            'Не се показва директно, но определя кои часове се предлагат на клиентите при '
            'резервация с този терапевт в този ден.'
        ),
    )

    class Meta:
        unique_together = ('specialist', 'day_of_week')
        verbose_name = _('Работно време')
        verbose_name_plural = _('Работно време')

    def __str__(self):
        return f"{self.specialist.name} - {self.get_day_of_week_display()}"

DESCRIPTION_LONG_THRESHOLD_CHARS = 500

class BusinessInfo(models.Model):
    name = models.CharField(
        max_length=255,
        help_text=_('Използва се като алтернативен текст (alt) на снимката на студиото в страница "За нас".'),
    )
    description = models.TextField(
        help_text=_('Показва се като основен текст в страница "За нас".'),
    )
    main_image = models.ImageField(
        upload_to='business/',
        help_text=_(
            'Снимката се показва в естествените си пропорции (без изрязване), с ограничена '
            'максимална ширина. За симетричен и професионален вид препоръчваме портретна или '
            'квадратна снимка (съотношение между 3:4 и 1:1), минимум 800px на по-късата страна. '
            'Много издължени (панорамни или тесни) снимки могат да изглеждат непропорционално до текста. '
            'Показва се като главна снимка в страница "За нас".'
        ),
    )
    address = models.CharField(
        max_length=255,
        help_text=_('Показва се в контактната карта в профила на клиента и в долния колонтитул (footer) на сайта.'),
    )
    phone = models.CharField(
        max_length=50,
        blank=True,
        help_text=_(
            'Показва се в профила на клиента и в долния колонтитул (footer) на сайта '
            'като линк за обаждане.'
        ),
    )
    email_address = models.EmailField(
        help_text=_('Показва се в долния колонтитул (footer) на сайта като mailto линк.'),
    )
    facebook_link = models.URLField(
        null=True, blank=True,
        help_text=_('Показва се като социална икона в долния колонтитул (footer) на сайта.'),
    )
    instagram_link = models.URLField(
        null=True, blank=True,
        help_text=_('Показва се като социална икона в долния колонтитул (footer) на сайта.'),
    )
    tik_tok_link = models.URLField(
        null=True, blank=True,
        help_text=_('Показва се като социална икона в долния колонтитул (footer) на сайта.'),
    )
    stats = JSONField(
        default=dict,
        blank=True,
        help_text=_(
            'JSON обект с показатели (изберете кои да покажете, останалите се скриват): '
            '{"years_of_practice": "8+", "clients_served": "500+", "average_rating": "4.9", "certifications_count": "12"}. '
            'years_of_practice, clients_served и certifications_count се показват като карти с показатели в страница "За нас".'
        ),
    )
    credentials = JSONField(
        default=dict,
        blank=True,
        help_text=_(
            'JSON обект с два списъка — "training" и "recognition". Всеки елемент: title, subtitle, '
            'по избор year и description. Празен списък скрива съответната група. Пример: '
            '{"training": [{"title": "Шведски масаж", "subtitle": "Виенски институт", "year": "2019", "description": "..."}], "recognition": []}. '
            'Показва се като секция "Обучения/Признания" в страница "За нас".'
        ),
    )
    faq = JSONField(
        default=list,
        blank=True,
        help_text=_(
            'JSON списък от въпроси и отговори. Празен списък скрива секцията. Пример: '
            '[{"question": "Приемате ли без резервация?", "answer": "Не, само с предварителна резервация."}]. '
            'Показва се като разгъващ се списък с въпроси и отговори в страница "За нас".'
        ),
    )

    class Meta:
        verbose_name = _('Студио')
        verbose_name_plural = _('Студиа')

    def __str__(self):
        return self.name

    @property
    def is_description_long(self):
        return len(strip_tags(self.description or '')) > DESCRIPTION_LONG_THRESHOLD_CHARS

class Reservation(models.Model):
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

    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='reservations',
        help_text=_('Показва се в потвърждението на резервацията и в списъка с резервации в профила на клиента.'),
    )

    specialist = models.ForeignKey(
        Specialist,
        on_delete=models.CASCADE,
        related_name='reservations',
        help_text=_('Показва се в потвърждението на резервацията и в списъка с резервации в профила на клиента.'),
    )

    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='reservations'
    )

    time = models.TimeField(
        help_text=_('Показва се в потвърждението на резервацията и в списъка с резервации в профила на клиента.'),
    )
    date = models.DateField(
        db_index=True,
        help_text=_('Показва се в потвърждението на резервацията и в списъка с резервации в профила на клиента.'),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
        help_text=_(
            'Определя дали резервацията се показва като предстояща или минала в профила на '
            'клиента (или изобщо не се показва, ако е отказана).'
        ),
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
    additional_text = models.TextField(
        default='', blank=True, max_length=500, validators=[MaxLengthValidator(500)],
        help_text=_('Показва се на клиента при преглед, редакция или отказ на резервацията му.'),
    )

    gallery = models.OneToOneField(
        "Gallery",
        on_delete=models.CASCADE,
        related_name='reservations',
        null=True,
        blank=True,
    )

    need_client_review = models.BooleanField(
        default=False,
        help_text=_(
            'Отбележете, когато галерията е готова и клиентът трябва да прегледа и '
            'маркира снимките си в профила си. Показва се на страницата за преглед на '
            'снимки в профила на клиента, докато отметката е включена — автоматично '
            'се изключва, след като клиентът финализира избора си.'
        ),
    )

    send_user_notification_on_gallery_creation = models.BooleanField(
        default=False,
        help_text=_('Да бъде ли изпратено уведомление до клиента при създаване на галерия?')
    )

    proofing_finalized_at = models.DateTimeField(
        null=True, blank=True,
        help_text=_(
            'Кога клиентът е финализирал избора на снимки от страницата за преглед на '
            'снимки от резервацията си. Докато е попълнено, клиентът вижда страницата '
            'като заключена за преглед.'
        ),
    )
    # Custom Managers
    class ReservationQuerySet(models.QuerySet):
        def active(self):
            return self.filter(status='active').select_related('service', 'specialist')
        def past(self):
            return self.filter(status__in=['completed', 'no_show']).select_related('service', 'specialist')
        def deleted(self):
            return self.filter(status='deleted')

    class ReservationManager(models.Manager):
        def get_queryset(self):
            return Reservation.ReservationQuerySet(self.model, using=self._db).exclude(status='deleted')
        def active(self):
            return self.get_queryset().active()
        def past(self):
            return self.get_queryset().past()

    objects = ReservationManager()
    all_objects = models.Manager()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Snapshot of the as-loaded values (set from DB via from_db(), or left
        # as the field defaults for a brand-new instance) so clean() can tell
        # a genuine reschedule/new booking apart from an edit to an unrelated
        # field on an already-valid active reservation.
        self._loaded_date = self.date
        self._loaded_time = self.time
        self._loaded_status = self.status

    @property
    def end_time(self):
        start_dt = datetime.combine(self.date, self.time)
        duration = timedelta(minutes=self.service.duration_in_minutes)
        return (start_dt + duration).time()

    def clean(self):
        # Use _id to avoid RelatedObjectDoesNotExist if the field is not set
        if not all([self.service_id, self.specialist_id, self.date, self.time]):
            return

        # 0. Only validate Active reservations for overlaps
        if self.status != self.STATUS_ACTIVE:
            return

        start_dt = datetime.combine(self.date, self.time)
        duration = timedelta(minutes=self.service.duration_in_minutes)
        end_dt = start_dt + duration

        # 1. Lead time check (2 hours) — only for a new booking, a reschedule
        # (date/time changed), or a transition into active. Editing an
        # unrelated field on an already-active, already-valid reservation
        # shouldn't be blocked just because it's now within the lead time.
        is_new_or_rescheduled = (
            self.pk is None
            or self.date != self._loaded_date
            or self.time != self._loaded_time
            or self._loaded_status != self.STATUS_ACTIVE
        )
        if is_new_or_rescheduled:
            reservation_datetime = timezone.make_aware(start_dt)
            if reservation_datetime < timezone.now() + timedelta(hours=2):
                raise ValidationError(_("Резервация трябва да се направи поне 2 часа предварително."))

        # 2. Working hours check
        day = self.date.weekday()
        hours = self.specialist.working_hours.filter(day_of_week=day).first()
        if not hours:
            raise ValidationError(_("%(name)s не работи в този ден.") % {'name': self.specialist.name})

        # Compare full datetimes (not bare .time()) so a duration that pushes
        # the end past midnight is correctly detected as outside working
        # hours, instead of wrapping around to an early clock time.
        hours_start_dt = datetime.combine(self.date, hours.start_time)
        hours_end_dt = datetime.combine(self.date, hours.end_time)

        if start_dt < hours_start_dt or end_dt > hours_end_dt:
            raise ValidationError(
                _("Избраният час е извън работното време на %(name)s (%(start)s - %(end)s).") % {
                    'name': self.specialist.name,
                    'start': hours.start_time,
                    'end': hours.end_time,
                }
            )

        # 3. Overlap check
        existing_reservations = Reservation.objects.select_related('service').filter(
            specialist=self.specialist,
            date=self.date,
            status=self.STATUS_ACTIVE
        ).exclude(pk=self.pk)

        for res in existing_reservations:
            res_duration = timedelta(minutes=res.service.duration_in_minutes)
            res_start_dt = datetime.combine(res.date, res.time)
            res_end_dt = res_start_dt + res_duration

            # (StartA < EndB) and (EndA > StartB)
            if start_dt < res_end_dt and end_dt > res_start_dt:
                raise ValidationError(
                    _("Часът се застъпва с друга резервация за %(name)s.") % {'name': self.specialist.name}
                )

    def change_status(self, new_status, user=None):
        self.status = new_status
        self.status_updated_at = timezone.now()
        if user:
            self.status_updated_by = user
        self.save()

    @property
    def is_proofing_finalized(self):
        return self.proofing_finalized_at is not None

    def finalize_proofing(self):
        self.proofing_finalized_at = timezone.now()
        self.need_client_review = False
        self.save(update_fields=['proofing_finalized_at', 'need_client_review'])

    def unlock_proofing(self):
        self.proofing_finalized_at = None
        self.need_client_review = True
        self.save(update_fields=['proofing_finalized_at', 'need_client_review'])

    def save(self, *args, **kwargs):
        if self.status == self.STATUS_ACTIVE and self.specialist_id:
            with transaction.atomic():
                # Lock the specialist row so concurrent bookings for them serialize,
                # closing the check-then-save race in clean()'s overlap check.
                Specialist.objects.select_for_update().get(pk=self.specialist_id)
                self.full_clean()
                super().save(*args, **kwargs)
        else:
            self.full_clean()
            super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('Резервация')
        verbose_name_plural = _('Резервации')
        constraints = [
            models.UniqueConstraint(
                fields=['specialist', 'date', 'time'],
                condition=models.Q(status='active'),
                name='unique_active_reservation_slot',
            )
        ]
        permissions = [
            ('view_all_reservations', 'Can view all reservations across all specialists'),
            ('view_specialist_reservations', 'Can view own specialist reservations'),
        ]

    def __str__(self):
        return f"{self.service.name} - {self.date} {self.time.strftime('%H:%M')}"

class Gallery(models.Model):
    TYPE_HOMEPAGE = 'homepage'
    TYPE_RESERVATION = 'reservation'
    TYPE_ALBUM = 'album'
    TYPE_CHOICES = [
        (TYPE_HOMEPAGE, _('Начална страница')),
        (TYPE_RESERVATION, _('Резервация')),
        (TYPE_ALBUM, _('Албум')),
    ]

    gallery_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default=TYPE_ALBUM,
        verbose_name=_('Тип галерия'),
        help_text=_(
            'Определя къде се показва тази галерия: "Начална страница" — секцията с '
            'галерия на началната страница (може да има само една); "Резервация" — '
            'снимки, свързани с конкретна резервация; "Албум" — показва се като '
            'самостоятелен албум на страницата с галерии.'
        ),
    )
    title = models.CharField(
        max_length=255, blank=True, verbose_name=_('Заглавие'),
        help_text=_(
            'За албуми: показва се като заглавие на албума на страницата с галерии и на '
            'собствената му страница (задължително за албуми). За началната страница: '
            'показва се като малък надпис над секцията с галерия.'
        ),
    )
    description = models.TextField(
        blank=True, verbose_name=_('Описание'),
        help_text=_(
            'За албуми: показва се на собствената страница на албума, а за първия по ред '
            'албум — и в плочката му на страницата с галерии. За началната страница: '
            'показва се като заглавие на секцията с галерия.'
        ),
    )
    slug = models.SlugField(
        unique=True, null=True, blank=True, verbose_name=_('Slug'),
        help_text=_(
            'Използва се за изграждане на адреса (URL) на страницата на албума. '
            'Не се използва за другите типове галерии.'
        ),
    )
    order = models.PositiveIntegerField(
        default=0, verbose_name=_('Ред'),
        help_text=_('Определя реда, в който албумите се показват на страницата с галерии.'),
    )

    class Meta:
        ordering = ['order']
        verbose_name = _('Галерия')
        verbose_name_plural = _('Галерии')

    def clean(self):
        if self.gallery_type == self.TYPE_HOMEPAGE:
            qs = Gallery.objects.filter(gallery_type=self.TYPE_HOMEPAGE)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({
                    'gallery_type': _('Може да има само една галерия от тип "Начална страница".')
                })
        if self.gallery_type == self.TYPE_ALBUM and not self.title:
            raise ValidationError({'title': _('Заглавието е задължително за галерии от тип "Албум".')})

    def __str__(self):
        if self.gallery_type == self.TYPE_HOMEPAGE and hasattr(self, 'home_page'):
            return f"{_('Галерия')} - {self.home_page.brand_name}"
        return self.title or f"{_('Галерия')} {self.id}"

    @property
    def cover(self):
        return self.images.order_by('order').first()

    @property
    def photo_count(self):
        return self.images.count()


class Image(models.Model):
    CROP_TOP = 'top'
    CROP_CENTER = 'center'
    CROP_BOTTOM = 'bottom'
    CROP_CHOICES = [
        (CROP_TOP, _('Горе')),
        (CROP_CENTER, _('В центъра')),
        (CROP_BOTTOM, _('Долу')),
    ]

    MIN_DIMENSION = 600
    MAX_DIMENSION = 2560
    WEBP_QUALITY = 80

    gallery = models.ForeignKey(
        'Gallery', on_delete=models.CASCADE, related_name='images',
        verbose_name=_('Галерия'),
    )
    image = models.ImageField(
        upload_to='gallery/photos/',
        help_text=_(
            'Показва се в секцията с галерия на началната страница, или на страницата на '
            'албума (и като корична снимка на албума на страницата с галерии, ако е '
            'първата по ред). Оразмерява се и се компресира автоматично при качване — '
            'няма нужда снимката да бъде обработена предварително.'
        ),
    )
    crop_position = models.CharField(
        max_length=10, choices=CROP_CHOICES, default=CROP_CENTER,
        verbose_name=_('Позиция при изрязване'),
        help_text=_(
            'Определя коя част от снимката да остане видима, когато тя бъде изрязана да '
            'пасне на рамка — в секцията с галерия и началния банер на началната страница, '
            'и в плочките на страницата с галерии. Използвайте, ако важната част от '
            'снимката е отрязана при показването й.'
        ),
    )
    alt_text = models.CharField(
        max_length=255, blank=True,
        help_text=_('Използва се като алтернативен текст (alt) за тази снимка.'),
    )
    order = models.PositiveIntegerField(
        default=0, verbose_name=_('Ред'),
        help_text=_(
            'Определя реда, в който снимките се показват в галерията/албума, и коя се '
            'използва като корична (първата по ред).'
        ),
    )

    class Meta:
        ordering = ['order']
        verbose_name = _('Изображение')
        verbose_name_plural = _('Изображения')

    def __str__(self):
        return self.alt_text or f"Снимка {self.order}"

    def clean(self):
        super().clean()
        if self.image and not self.image._committed:
            self.image.seek(0)
            with PILImage.open(self.image) as img:
                width, height = img.size
            self.image.seek(0)
            if min(width, height) < self.MIN_DIMENSION:
                raise ValidationError({
                    'image': _(
                        'Снимката е твърде малка (%(width)dx%(height)d px). '
                        'Минималният размер е %(min)dpx от по-късата страна.'
                    ) % {'width': width, 'height': height, 'min': self.MIN_DIMENSION}
                })

    def save(self, *args, **kwargs):
        # _committed is False only for a freshly assigned upload, never for a FieldFile
        # loaded from an existing row — this keeps re-saves of unrelated fields cheap.
        if self.image and not self.image._committed:
            self._process_image()
        super().save(*args, **kwargs)

    def _process_image(self):
        self.image.seek(0)
        with PILImage.open(self.image) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGB')
            width, height = img.size
            longest = max(width, height)
            if longest > self.MAX_DIMENSION:
                scale = self.MAX_DIMENSION / longest
                img = img.resize(
                    (round(width * scale), round(height * scale)), PILImage.Resampling.LANCZOS,
                )
            buffer = BytesIO()
            img.save(buffer, format='WEBP', quality=self.WEBP_QUALITY)
        new_name = os.path.splitext(self.image.name)[0] + '.webp'
        self.image = ContentFile(buffer.getvalue(), name=new_name)


class PhotoLabel(models.Model):
    gallery = models.ForeignKey(
        Gallery, on_delete=models.CASCADE, related_name='photo_labels',
        verbose_name=_('Галерия'),
    )
    name = models.CharField(
        max_length=100, verbose_name=_('Име'),
        help_text=_(
            'Името на етикета, който клиентът вижда и може да прикачи към снимки при '
            'преглед на снимките от своята резервация.'
        ),
    )
    cap = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name=_('Максимален брой'),
        help_text=_(
            'Максимален брой снимки, които клиентът може да маркира с този етикет при '
            'преглед на снимките от своята резервация.'
        ),
    )
    order = models.PositiveIntegerField(
        default=0, verbose_name=_('Ред'),
        help_text=_(
            'Определя реда, в който етикетите се показват на клиента при преглед на '
            'снимките от своята резервация.'
        ),
    )

    class Meta:
        ordering = ['order']
        verbose_name = _('Етикет за преглед на снимки')
        verbose_name_plural = _('Етикети за преглед на снимки')

    def __str__(self):
        return self.name


class ImageProof(models.Model):
    image = models.OneToOneField(Image, on_delete=models.CASCADE, related_name='proof')
    is_marked = models.BooleanField(
        default=False,
        help_text=_(
            'Дали клиентът е маркирал тази снимка като любима при преглед на '
            'снимките от своята резервация.'
        ),
    )
    comment = models.TextField(
        blank=True, default='', validators=[MaxLengthValidator(2000)],
        help_text=_(
            'Забележка или коментар, което клиентът е написал за тази снимка при преглед на '
            'снимките от своята резервация.'
        ),
    )
    labels = models.ManyToManyField(
        PhotoLabel, blank=True, related_name='images',
        help_text=_(
            'Етикетите, които клиентът е избрал за тази снимка при преглед на '
            'снимките от своята резервация.'
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Избор на клиент за снимка')
        verbose_name_plural = _('Избори на клиенти за снимки')

    def __str__(self):
        return f'ImageProof({self.image_id})'


class HomePage(models.Model):
    brand_name = models.CharField(
        max_length=255,
        help_text=_(
            'Показва се като име на сайта в началния банер, в алтернативния текст (alt) на '
            'логото в горния колонтитул, в реда за авторски права в долния колонтитул '
            '(footer), както и в имейлите до клиентите (кодове за резервация, смяна на парола).'
        ),
    )
    description = models.TextField(
        help_text=_('Показва се като подзаглавие в началния банер на началната страница.'),
    )
    logo = models.ImageField(
        upload_to='branding/', null=True, blank=True,
        help_text=_('Показва се като лого в горния колонтитул на сайта и в имейлите до клиентите.'),
    )
    gallery = models.OneToOneField(
        Gallery,
        on_delete=models.CASCADE,
        related_name='home_page'
    )
    privacy_policy_content = models.TextField(
        null=True, blank=True,
        help_text=_('Показва се изцяло на страницата "Политика за поверителност".'),
    )
    footer_tagline = models.TextField(
        blank=True,
        help_text=_('Показва се като кратък текст (tagline) в долния колонтитул (footer) на сайта.'),
    )

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
                'gallery': Gallery.objects.create,
            }
        )
        return obj

    def __str__(self):
        return self.brand_name


class BusinessWorkingHours(models.Model):
    home_page = models.ForeignKey(
        HomePage,
        on_delete=models.CASCADE,
        related_name='business_working_hours',
    )
    day_label = models.CharField(
        max_length=100,
        verbose_name=_('Ден / период'),
        help_text=_(
            'напр. "Понеделник до Петък". Показва се в списъка "Работно време" на началната '
            'страница и в профила на клиента.'
        ),
    )
    hours = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Часове'),
        help_text=_(
            'напр. "9:00 - 18:00" — оставете празно за "Почивен ден". Показва се в списъка '
            '"Работно време" на началната страница и в профила на клиента.'
        ),
    )
    order = models.PositiveSmallIntegerField(
        default=0, verbose_name=_('Ред'),
        help_text=_('Определя реда, в който тези редове се показват.'),
    )

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
        'Reservation',
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
        help_text=_('Показва се като име на автора в секцията с отзиви на началната страница и на страницата с всички отзиви.'),
    )

    content = models.TextField(
        max_length=2000, validators=[MaxLengthValidator(2000)],
        help_text=_('Показва се като текст на отзива в секцията с отзиви на началната страница и на страницата с всички отзиви.'),
    )

    rating = models.IntegerField(
        default=5,
        help_text=_('Показва се като звезден рейтинг в секцията с отзиви на началната страница.'),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_('Показва се като дата на отзива на страницата с всички отзиви.'),
    )

    is_reviewed = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_(
            'Трябва да е отметнато, за да се показва този отзив публично в секцията с отзиви '
            'на началната страница и на страницата с всички отзиви.'
        ),
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


_HEX_COLOR_VALIDATOR = RegexValidator(
    regex=r'^#[0-9A-Fa-f]{6}$',
    message=_('Въведете валиден HEX цвят, напр. #4A3728.'),
)


class SiteConfiguration(models.Model):
    FONT_PAIR_CHOICES = [
        ('playfair_montserrat', _('Playfair Display + Montserrat')),
        ('cormorant_lato', _('Cormorant Garamond + Lato')),
        ('poppins_opensans', _('Poppins + Open Sans')),
        ('merriweather_sourcesans', _('Merriweather + Source Sans 3')),
        ('raleway_roboto', _('Raleway + Roboto')),
    ]

    STYLE_PRESET_CHOICES = [
        ('soft', _('Мек (текущи radius и сенки)')),
        ('sharp', _('Остър (минимални radius, плоски сенки)')),
        ('round', _('Заоблен (pill бутони, големи radius)')),
    ]

    HERO_VARIANT_CHOICES = [
        ('split', _('Split — текст и снимка една до друга')),
        ('carousel', _('Carousel — въртяща се галерия')),
        ('fullbleed', _('Fullbleed — снимка на цяла ширина')),
    ]

    COLOR_PRESET_CHOICES = [('custom', _('Персонализирано'))] + [
        (key, preset['label']) for key, preset in COLOR_PRESETS.items()
    ]

    color_preset = models.CharField(
        max_length=30, choices=COLOR_PRESET_CHOICES, default='custom', blank=True,
        verbose_name=_('Готова цветова комбинация'),
        help_text=_(
            'Изберете готова цветова комбинация, за да зададете наведнъж всички цветове по-долу. '
            'Прилага се на всички страници на сайта.'
        ),
    )

    primary_color = models.CharField(
        max_length=7, default='#4A3728', validators=[_HEX_COLOR_VALIDATOR],
        verbose_name=_('Основен цвят'),
        help_text=_('Цвят по цялата тема на сайта, използван на всички страници.'),
    )
    primary_light_color = models.CharField(
        max_length=7, default='#6D5442', validators=[_HEX_COLOR_VALIDATOR],
        verbose_name=_('Основен цвят (светъл)'),
        help_text=_('Цвят по цялата тема на сайта, използван на всички страници.'),
    )
    secondary_color = models.CharField(
        max_length=7, default='#C2A38E', validators=[_HEX_COLOR_VALIDATOR],
        verbose_name=_('Вторичен цвят'),
        help_text=_('Цвят по цялата тема на сайта, използван на всички страници.'),
    )
    accent_color = models.CharField(
        max_length=7, default='#8E735B', validators=[_HEX_COLOR_VALIDATOR],
        verbose_name=_('Акцентен цвят'),
        help_text=_('Цвят по цялата тема на сайта, използван на всички страници.'),
    )
    background_color = models.CharField(
        max_length=7, default='#FAF7F2', validators=[_HEX_COLOR_VALIDATOR],
        verbose_name=_('Фон'),
        help_text=_('Цвят по цялата тема на сайта, използван на всички страници.'),
    )
    text_color = models.CharField(
        max_length=7, default='#2D241E', validators=[_HEX_COLOR_VALIDATOR],
        verbose_name=_('Текст'),
        help_text=_('Цвят по цялата тема на сайта, използван на всички страници.'),
    )
    text_muted_color = models.CharField(
        max_length=7, default='#6B5E55', validators=[_HEX_COLOR_VALIDATOR],
        verbose_name=_('Текст (приглушен)'),
        help_text=_('Цвят по цялата тема на сайта, използван на всички страници.'),
    )
    border_color = models.CharField(
        max_length=7, default='#4A3728', validators=[_HEX_COLOR_VALIDATOR],
        verbose_name=_('Цвят на рамки'),
        help_text=_('Цвят по цялата тема на сайта, използван на всички страници.'),
    )

    font_pair = models.CharField(
        max_length=30, choices=FONT_PAIR_CHOICES, default='playfair_montserrat',
        verbose_name=_('Двойка шрифтове'),
        help_text=_('Шрифт по цялата тема на сайта, използван на всички страници.'),
    )
    style_preset = models.CharField(
        max_length=10, choices=STYLE_PRESET_CHOICES, default='soft',
        verbose_name=_('Стил (форми и сенки)'),
        help_text=_('Стил на форми и сенки (заобляне на ъгли, бутони, карти) по цялата тема на сайта.'),
    )
    hero_variant = models.CharField(
        max_length=10, choices=HERO_VARIANT_CHOICES, default='split',
        verbose_name=_('Начален банер'),
        help_text=_('Определя кой изглед на банера се използва на началната страница.'),
    )

    service_singular = models.CharField(
        max_length=50, default='услуга', verbose_name=_('Услуга (ед. число)'),
        help_text=_('Използва се навсякъде, където сайтът се обръща към "услуга" — напр. страницата за резервация и профила на клиента.'),
    )
    service_plural = models.CharField(
        max_length=50, default='услуги', verbose_name=_('Услуги (мн. число)'),
        help_text=_('Използва се навсякъде, където сайтът се обръща към "услуги" — напр. страницата за резервация и профила на клиента.'),
    )
    specialist_singular = models.CharField(
        max_length=50, default='специалист', verbose_name=_('Специалист (ед. число)'),
        help_text=_('Използва се навсякъде, където сайтът се обръща към "специалист" — напр. страницата за резервация и профила на клиента.'),
    )
    specialist_plural = models.CharField(
        max_length=50, default='специалисти', verbose_name=_('Специалисти (мн. число)'),
        help_text=_('Използва се навсякъде, където сайтът се обръща към "специалисти" — напр. страницата за резервация и профила на клиента.'),
    )

    booking_enabled = models.BooleanField(
        default=True, verbose_name=_('Резервации активни'),
        help_text=_(
            'Когато е изключено, скрива всички бутони/линкове за резервация по целия сайт '
            '(горно меню, начална страница, страница с услуги, профил на клиента).'
        ),
    )
    comments_enabled = models.BooleanField(
        default=True, verbose_name=_('Коментари активни'),
        help_text=_('Когато е изключено, скрива секцията с отзиви на началната страница.'),
    )
    google_login_enabled = models.BooleanField(
        default=True, verbose_name=_('Вход с Google активен'),
        help_text=_('Когато е изключено, скрива опцията "Вход с Google" в модала за вход.'),
    )

    class Meta:
        verbose_name = _('Настройки на сайта')
        verbose_name_plural = _('Настройки на сайта')

    def save(self, *args, **kwargs):
        if not self.pk and SiteConfiguration.objects.exists():
            return
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return str(self._meta.verbose_name)

