import csv
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Max
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import format_html
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import date

from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.decorators import action
from modeltranslation.admin import TabbedTranslationAdmin

from massageProject.main_app.models import (
    Service, Image, Gallery, HomePage,
    BusinessInfo, Specialist, WorkingHours, Reservation, Comment,
    BusinessWorkingHours, ServiceGroup,
    SiteConfiguration, PhotoLabel,
)

# --- Forms ---

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """FileField that accepts and cleans a list of files (Django's
    documented recipe for native multi-file <input> support — Django has no
    built-in multi-file form field)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        if self.required and not result:
            raise ValidationError(self.error_messages['required'], code='required')
        return result


class GalleryBulkImageUploadForm(forms.Form):
    images = MultipleFileField(label=_('Снимки'))

# --- Actions ---

@admin.action(description=_('Export selected reservations to CSV'))
def export_reservations_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="reservations_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'User', 'Service', 'Specialist', 'Date', 'Time', 'Additional Text'])

    for obj in queryset.select_related('user', 'service', 'specialist'):
        writer.writerow([obj.id, obj.user.get_full_name(), obj.service.name, obj.specialist.name, obj.date, obj.time, obj.additional_text])

    return response

@admin.action(description=_('Mark selected comments as reviewed'))
def mark_as_reviewed(modeladmin, request, queryset):
    queryset.update(is_reviewed=True)

def _bulk_change_status(modeladmin, request, queryset, new_status):
    skipped = queryset.filter(status=Reservation.STATUS_DELETED).count()
    # A single UPDATE instead of per-row change_status()/full_clean(): safe
    # here because the target status is never 'active', so clean() would
    # only ever hit its early-return branch anyway.
    queryset.exclude(status=Reservation.STATUS_DELETED).update(
        status=new_status,
        status_updated_at=timezone.now(),
        status_updated_by=request.user,
    )
    if skipped:
        modeladmin.message_user(
            request,
            _('Пропуснати %(count)d отказани резервации (не могат да бъдат маркирани).') % {'count': skipped},
            level=messages.WARNING,
        )

@admin.action(description=_('Маркирай като Завършена'))
def mark_as_completed(modeladmin, request, queryset):
    _bulk_change_status(modeladmin, request, queryset, Reservation.STATUS_COMPLETED)

@admin.action(description=_('Маркирай като Не се е явил'))
def mark_as_noshow(modeladmin, request, queryset):
    _bulk_change_status(modeladmin, request, queryset, Reservation.STATUS_NOSHOW)

@admin.action(description=_('Отключи прегледа на снимки'))
def unlock_photo_proofing(modeladmin, request, queryset):
    for reservation in queryset:
        if reservation.is_proofing_finalized:
            reservation.unlock_proofing()

# --- Filters ---

class ReservationDateFilter(admin.SimpleListFilter):
    title = _('Времеви период')
    parameter_name = 'timeframe'

    def lookups(self, request, modeladmin):
        return (
            ('today', _('Днес')),
            ('upcoming', _('Предстоящи')),
            ('past', _('Минали')),
        )

    def queryset(self, request, queryset):
        today = date.today()
        if self.value() == 'today':
            return queryset.filter(date=today)
        if self.value() == 'upcoming':
            return queryset.filter(date__gt=today)
        if self.value() == 'past':
            return queryset.filter(date__lt=today)

# --- Admin Classes ---

@admin.register(ServiceGroup)
class ServiceGroupAdmin(ModelAdmin, TabbedTranslationAdmin):
    list_display = ('name', 'order')
    list_editable = ('order',)


@admin.register(Service)
class ServiceAdmin(ModelAdmin, TabbedTranslationAdmin):
    list_display = ('name', 'price', 'duration_in_minutes', 'home_page', 'group')
    search_fields = ('name', 'short_description')
    list_filter = ('home_page', 'group', 'price', 'duration_in_minutes')
    list_editable = ('price', 'duration_in_minutes', 'home_page')
    list_filter_sheet = True

    fieldsets = (
        (_('Основна информация'), {'fields': ('name', 'short_description', 'description')}),
        (_('Цена и Продължителност'), {'fields': ('price', 'duration_in_minutes')}),
        (_('Медия и Видимост'), {'fields': ('image', 'home_page', 'group')}),
    )

    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />', obj.image.url)
        return _("Няма снимка")
    display_image.short_description = _('Преглед')

@admin.register(Specialist)
class SpecialistAdmin(ModelAdmin, TabbedTranslationAdmin):
    list_display = ('display_image', 'name', 'phone_number', 'email', 'user')
    search_fields = ('name', 'email', 'phone_number')
    autocomplete_fields = ('user',)

    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 50%;" />', obj.image.url)
        return _("Няма снимка")
    display_image.short_description = _('Снимка')

@admin.register(WorkingHours)
class WorkingHoursAdmin(ModelAdmin):
    list_display = ('specialist', 'get_day_display', 'start_time', 'end_time')
    list_filter = ('day_of_week', 'specialist')
    list_editable = ('start_time', 'end_time')
    ordering = ('specialist', 'day_of_week')
    list_filter_sheet = True

    def get_day_display(self, obj):
        return dict(WorkingHours.DAYS_OF_WEEK).get(obj.day_of_week)
    get_day_display.short_description = _('Ден')

@admin.register(Reservation)
class ReservationAdmin(ModelAdmin):
    list_display = ('date', 'time', 'get_client_name', 'service', 'specialist', 'status', 'status_updated_at', 'need_client_review')
    list_filter = ('status', ReservationDateFilter, 'specialist', 'service', 'date', 'need_client_review')
    search_fields = ('user__phone_number', 'user__first_name', 'user__last_name', 'service__name')
    date_hierarchy = 'date'
    actions = [export_reservations_csv, mark_as_completed, mark_as_noshow, unlock_photo_proofing]
    readonly_fields = ('updated_at', 'status_updated_at', 'status_updated_by', 'proofing_finalized_at')
    list_filter_sheet = True

    fieldsets = (
        (_('Детайли за резервацията'), {'fields': ('date', 'time', 'user', 'status')}),
        (_('Информация за услугата'), {'fields': ('service', 'specialist')}),
        (_('Допълнителни бележки'), {'fields': ('additional_text',)}),
        (_('Системен одит'), {'fields': ('updated_at', 'status_updated_at', 'status_updated_by', 'proofing_finalized_at'), 'classes': ('collapse',)}),
        (_('Галерия'), {'fields': ('gallery', 'need_client_review')}),
    )

    def get_client_name(self, obj):
        return obj.user.get_full_name() or obj.user.phone_number
    get_client_name.short_description = _('Клиент')

    def get_queryset(self, request):
        return Reservation.all_objects.all()

    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data:
            # Route through the model's own change_status() so audit
            # stamping stays in one place instead of being reimplemented here.
            obj.change_status(obj.status, user=request.user)
        else:
            super().save_model(request, obj, form, change)

@admin.register(Comment)
class CommentAdmin(ModelAdmin):
    list_display = ('author', 'content_truncated', 'created_at', 'is_reviewed')
    list_filter = ('is_reviewed', 'created_at')
    search_fields = ('author', 'content')
    ordering = ('is_reviewed', '-created_at')
    actions = [mark_as_reviewed]
    list_editable = ('is_reviewed',)
    list_filter_sheet = True

    def content_truncated(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_truncated.short_description = _('Съдържание')

@admin.register(Image)
class ImageAdmin(ModelAdmin, TabbedTranslationAdmin):
    list_display = ('display_image', 'gallery', 'alt_text', 'order')
    list_editable = ('order',)
    list_filter = ('gallery',)
    search_fields = ('alt_text',)

    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 80px; height: 50px; object-fit: cover;" />', obj.image.url)
        return _("Няма изображение")
    display_image.short_description = _('Преглед')


class ImageInline(TabularInline):
    model = Image
    extra = 1
    fields = ('image', 'alt_text', 'order')


class PhotoLabelInline(TabularInline):
    model = PhotoLabel
    extra = 1
    fields = ('name', 'cap', 'order')


@admin.register(Gallery)
class GalleryAdmin(ModelAdmin, TabbedTranslationAdmin):
    list_display = ('__str__', 'gallery_type', 'order', 'photo_count')
    list_editable = ('order',)
    list_filter = ('gallery_type',)
    prepopulated_fields = {'slug': ('title_bg',)}
    inlines = [ImageInline, PhotoLabelInline]
    fields = ('gallery_type', 'title', 'slug', 'description', 'order')
    actions_detail = ['bulk_upload_images']

    def photo_count(self, obj):
        return obj.photo_count
    photo_count.short_description = _('Брой снимки')

    @action(description=_('Качване на много снимки'), permissions=['change'])
    def bulk_upload_images(self, request, object_id, *args, **kwargs):
        gallery = get_object_or_404(Gallery, pk=object_id)
        image_validator = forms.ImageField()

        if request.method == 'POST':
            form = GalleryBulkImageUploadForm(request.POST, request.FILES)
            if form.is_valid():
                max_order = gallery.images.aggregate(Max('order'))['order__max']
                next_order = (max_order + 1) if max_order is not None else 0
                uploaded = 0
                for uploaded_file in form.cleaned_data['images']:
                    try:
                        image_validator.clean(uploaded_file)
                        image = Image(gallery=gallery, image=uploaded_file, order=next_order)
                        image.full_clean()
                        image.save()
                    except ValidationError as exc:
                        messages.error(
                            request,
                            _('Пропусната %(name)s: %(error)s') % {
                                'name': uploaded_file.name,
                                'error': '; '.join(exc.messages),
                            },
                        )
                        continue
                    uploaded += 1
                    next_order += 1
                if uploaded:
                    messages.success(request, _('Качени %(count)d снимки.') % {'count': uploaded})
                return redirect('admin:main_app_gallery_change', gallery.pk)
        else:
            form = GalleryBulkImageUploadForm()

        context = {
            **self.admin_site.each_context(request),
            'title': _('Качване на много снимки'),
            'opts': self.model._meta,
            'gallery': gallery,
            'form': form,
        }
        return render(request, 'admin/main_app/gallery/bulk_upload_images.html', context)


class BusinessWorkingHoursInline(TabularInline):
    model = BusinessWorkingHours
    extra = 1
    fields = ('day_label', 'hours', 'order')

@admin.register(HomePage)
class HomePageAdmin(ModelAdmin, TabbedTranslationAdmin):
    list_display = ('brand_name',)
    inlines = [BusinessWorkingHoursInline]
    fieldsets = (
        (None, {'fields': ('brand_name', 'logo', 'description', 'footer_tagline', 'gallery')}),
        (_('Политика за поверителност'), {'fields': ('privacy_policy_content',), 'classes': ('collapse',)}),
    )

@admin.register(BusinessInfo)
class BusinessInfosAdmin(ModelAdmin, TabbedTranslationAdmin):
    list_display = ('display_image', 'name', 'address', 'phone')
    list_filter_sheet = True
    DESCRIPTION_FIELDS = ('description', 'description_bg', 'description_en')

    def display_image(self, obj):
        if obj.main_image:
            return format_html('<img src="{}" style="width: 80px; height: 50px; object-fit: cover;" />', obj.main_image.url)
        return _("Няма изображение")
    display_image.short_description = _('Основна снимка')

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name in self.DESCRIPTION_FIELDS:
            formfield.widget = WysiwygWidget()
        return formfield

@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(ModelAdmin, TabbedTranslationAdmin):
    COLOR_FIELDS = (
        'primary_color', 'primary_light_color', 'secondary_color',
        'accent_color', 'background_color', 'text_color', 'text_muted_color',
        'border_color',
    )

    fieldsets = (
        (_('Тема — цветове'), {'fields': (
            'primary_color', 'primary_light_color', 'secondary_color',
            'accent_color', 'background_color', 'text_color', 'text_muted_color',
            'border_color',
        )}),
        (_('Типография и стил'), {'fields': ('font_pair', 'style_preset', 'hero_variant')}),
        (_('Терминология'), {'fields': (
            'service_singular', 'service_plural',
            'specialist_singular', 'specialist_plural',
        )}),
        (_('Функционалности'), {'fields': ('booking_enabled', 'comments_enabled', 'google_login_enabled')}),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name in self.COLOR_FIELDS:
            formfield.widget = forms.TextInput(attrs={'type': 'color'})
        return formfield

    def has_add_permission(self, request):
        return not SiteConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
