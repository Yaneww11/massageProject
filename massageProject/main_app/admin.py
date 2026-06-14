import csv
from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import date

from unfold.admin import ModelAdmin, TabularInline
from modeltranslation.admin import TabbedTranslationAdmin

from massageProject.main_app.models import (
    Massage, Image, Gallery, HomePage, GalleryImage,
    MessageStudio, Masseur, WorkingHours, MessageReservation, Comment,
    StudioWorkingHours,
)

# --- Actions ---

@admin.action(description=_('Export selected reservations to CSV'))
def export_reservations_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="reservations_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'User', 'Massage', 'Masseur', 'Date', 'Time', 'Additional Text'])
    
    for obj in queryset:
        writer.writerow([obj.id, obj.user.get_full_name(), obj.massage.name, obj.masseur.name, obj.date, obj.time, obj.additional_text])
    
    return response

@admin.action(description=_('Mark selected comments as reviewed'))
def mark_as_reviewed(modeladmin, request, queryset):
    queryset.update(is_reviewed=True)

@admin.action(description=_('Маркирай като Завършена'))
def mark_as_completed(modeladmin, request, queryset):
    for obj in queryset:
        obj.change_status(MessageReservation.STATUS_COMPLETED, user=request.user)

@admin.action(description=_('Маркирай като Не се е явил'))
def mark_as_noshow(modeladmin, request, queryset):
    for obj in queryset:
        obj.change_status(MessageReservation.STATUS_NOSHOW, user=request.user)

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

@admin.register(Massage)
class MassageAdmin(ModelAdmin, TabbedTranslationAdmin):
    list_display = ('name', 'price', 'duration_in_minutes', 'home_page')
    search_fields = ('name', 'short_description')
    list_filter = ('home_page', 'price', 'duration_in_minutes')
    list_editable = ('price', 'duration_in_minutes', 'home_page')
    list_filter_sheet = True
    
    fieldsets = (
        (_('Основна информация'), {'fields': ('name', 'short_description', 'description')}),
        (_('Цена и Продължителност'), {'fields': ('price', 'duration_in_minutes')}),
        (_('Медия и Видимост'), {'fields': ('image', 'home_page')}),
    )

    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />', obj.image.url)
        return _("Няма снимка")
    display_image.short_description = _('Преглед')

@admin.register(Masseur)
class MasseurAdmin(ModelAdmin, TabbedTranslationAdmin):
    list_display = ('display_image', 'name', 'phone_number', 'email')
    search_fields = ('name', 'email', 'phone_number')
    
    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 50%;" />', obj.image.url)
        return _("Няма снимка")
    display_image.short_description = _('Снимка')

@admin.register(WorkingHours)
class WorkingHoursAdmin(ModelAdmin):
    list_display = ('masseur', 'get_day_display', 'start_time', 'end_time')
    list_filter = ('day_of_week', 'masseur')
    list_editable = ('start_time', 'end_time')
    ordering = ('masseur', 'day_of_week')
    list_filter_sheet = True

    def get_day_display(self, obj):
        return dict(WorkingHours.DAYS_OF_WEEK).get(obj.day_of_week)
    get_day_display.short_description = _('Ден')

@admin.register(MessageReservation)
class MessageReservationAdmin(ModelAdmin):
    list_display = ('date', 'time', 'get_client_name', 'massage', 'masseur', 'status', 'status_updated_at')
    list_filter = ('status', ReservationDateFilter, 'masseur', 'massage', 'date')
    search_fields = ('user__phone_number', 'user__first_name', 'user__last_name', 'massage__name')
    date_hierarchy = 'date'
    actions = [export_reservations_csv, mark_as_completed, mark_as_noshow]
    readonly_fields = ('updated_at', 'status_updated_at', 'status_updated_by')
    list_filter_sheet = True
    
    fieldsets = (
        (_('Детайли за резервацията'), {'fields': ('date', 'time', 'user', 'status')}),
        (_('Информация за услугата'), {'fields': ('massage', 'masseur')}),
        (_('Допълнителни бележки'), {'fields': ('additional_text',)}),
        (_('Системен одит'), {'fields': ('updated_at', 'status_updated_at', 'status_updated_by'), 'classes': ('collapse',)}),
    )

    def get_client_name(self, obj):
        return obj.user.get_full_name() or obj.user.phone_number
    get_client_name.short_description = _('Клиент')

    def get_queryset(self, request):
        return MessageReservation.all_objects.all()

    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data:
            obj.status_updated_at = timezone.now()
            obj.status_updated_by = request.user
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
    list_display = ('display_image', 'alt_text')
    search_fields = ('alt_text',)

    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 80px; height: 50px; object-fit: cover;" />', obj.image.url)
        return _("Няма изображение")
    display_image.short_description = _('Преглед')

class GalleryImageInline(TabularInline):
    model = GalleryImage
    extra = 1

@admin.register(Gallery)
class GalleryAdmin(ModelAdmin):
    inlines = [GalleryImageInline]

class StudioWorkingHoursInline(TabularInline):
    model = StudioWorkingHours
    extra = 1
    fields = ('day_label', 'hours', 'order')

@admin.register(HomePage)
class HomePageAdmin(ModelAdmin, TabbedTranslationAdmin):
    list_display = ('brand_name',)
    inlines = [StudioWorkingHoursInline]
    fieldsets = (
        (None, {'fields': ('brand_name', 'logo', 'description', 'footer_tagline', 'gallery')}),
        (_('Политика за поверителност'), {'fields': ('privacy_policy_content',), 'classes': ('collapse',)}),
    )

@admin.register(MessageStudio)
class MessageStudiosAdmin(ModelAdmin, TabbedTranslationAdmin):
    list_display = ('display_image', 'name', 'address', 'phone')
    list_filter_sheet = True
    
    def display_image(self, obj):
        if obj.main_image:
            return format_html('<img src="{}" style="width: 80px; height: 50px; object-fit: cover;" />', obj.main_image.url)
        return _("Няма изображение")
    display_image.short_description = _('Основна снимка')
