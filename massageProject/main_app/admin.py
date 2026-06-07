import csv
from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import date
from massageProject.main_app.models import (
    Massage, Image, Gallery, HomePage, GalleryImage,
    MessageStudio, Masseur, WorkingHours, MessageReservation, Comment,
    StudioWorkingHours,
)

# --- Actions ---

@admin.action(description='Export selected reservations to CSV')
def export_reservations_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="reservations_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'User', 'Massage', 'Masseur', 'Date', 'Time', 'Additional Text'])
    
    for obj in queryset:
        writer.writerow([obj.id, obj.user.get_full_name(), obj.massage.name, obj.masseur.name, obj.date, obj.time, obj.additional_text])
    
    return response

@admin.action(description='Mark selected comments as reviewed')
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
    title = 'Timeframe'
    parameter_name = 'timeframe'

    def lookups(self, request, modeladmin):
        return (
            ('today', 'Today'),
            ('upcoming', 'Upcoming'),
            ('past', 'Past'),
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
class MassageAdmin(admin.ModelAdmin):
    list_display = ('display_image', 'name', 'price', 'duration_in_minutes', 'home_page')
    search_fields = ('name', 'short_description')
    list_filter = ('home_page', 'price', 'duration_in_minutes')
    list_editable = ('price', 'duration_in_minutes', 'home_page')
    fieldsets = (
        ('Basic Information', {'fields': ('name', 'short_description', 'description')}),
        ('Pricing & Duration', {'fields': ('price', 'duration_in_minutes')}),
        ('Media & Visibility', {'fields': ('image', 'home_page')}),
    )

    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />', obj.image.url)
        return "No Image"
    display_image.short_description = 'Preview'

@admin.register(Masseur)
class MasseurAdmin(admin.ModelAdmin):
    list_display = ('display_image', 'name', 'phone_number', 'email')
    search_fields = ('name', 'email', 'phone_number')
    
    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 50%;" />', obj.image.url)
        return "No Photo"
    display_image.short_description = 'Photo'

@admin.register(WorkingHours)
class WorkingHoursAdmin(admin.ModelAdmin):
    list_display = ('masseur', 'get_day_display', 'start_time', 'end_time')
    list_filter = ('day_of_week', 'masseur')
    list_editable = ('start_time', 'end_time')
    ordering = ('masseur', 'day_of_week')

    def get_day_display(self, obj):
        return dict(WorkingHours.DAYS_OF_WEEK).get(obj.day_of_week)
    get_day_display.short_description = 'Day'

@admin.register(MessageReservation)
class MessageReservationAdmin(admin.ModelAdmin):
    list_display = ('date', 'time', 'get_client_name', 'massage', 'masseur', 'status', 'status_updated_at')
    list_filter = ('status', ReservationDateFilter, 'masseur', 'massage', 'date')
    search_fields = ('user__phone_number', 'user__first_name', 'user__last_name', 'massage__name')
    date_hierarchy = 'date'
    actions = [export_reservations_csv, mark_as_completed, mark_as_noshow]
    readonly_fields = ('updated_at', 'status_updated_at', 'status_updated_by')
    
    fieldsets = (
        ('Reservation Details', {'fields': ('date', 'time', 'user', 'status')}),
        ('Service Info', {'fields': ('massage', 'masseur')}),
        ('Additional Notes', {'fields': ('additional_text',)}),
        ('System Audit', {'fields': ('updated_at', 'status_updated_at', 'status_updated_by'), 'classes': ('collapse',)}),
    )

    def get_client_name(self, obj):
        return obj.user.get_full_name() or obj.user.phone_number
    get_client_name.short_description = _('Клиент')

    def get_queryset(self, request):
        # Admins should see all reservations, including soft-deleted ones
        return MessageReservation.all_objects.all()

    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data:
            obj.status_updated_at = timezone.now()
            obj.status_updated_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'content_truncated', 'created_at', 'is_reviewed')
    list_filter = ('is_reviewed', 'created_at')
    search_fields = ('author', 'content')
    actions = [mark_as_reviewed]
    list_editable = ('is_reviewed',)

    def content_truncated(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_truncated.short_description = 'Content'

@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ('display_image', 'alt_text')
    search_fields = ('alt_text',)

    def display_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 80px; height: 50px; object-fit: cover;" />', obj.image.url)
        return "No Image"
    display_image.short_description = 'Preview'

class GalleryImageInline(admin.TabularInline):
    model = GalleryImage
    extra = 1

@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    inlines = [GalleryImageInline]

class StudioWorkingHoursInline(admin.TabularInline):
    model = StudioWorkingHours
    extra = 1
    fields = ('day_label', 'hours', 'order')


@admin.register(HomePage)
class HomePageAdmin(admin.ModelAdmin):
    list_display = ('title',)
    inlines = [StudioWorkingHoursInline]

@admin.register(MessageStudio)
class MessageStudiosAdmin(admin.ModelAdmin):
    list_display = ('display_image', 'name', 'address')
    
    def display_image(self, obj):
        if obj.main_image:
            return format_html('<img src="{}" style="width: 80px; height: 50px; object-fit: cover;" />', obj.main_image.url)
        return "No Image"
    display_image.short_description = 'Main Image'
