from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count, Q
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

UserModel = get_user_model()

@admin.register(UserModel)
class AppUserAdmin(ModelAdmin, UserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    list_display = ('email', 'full_name_display', 'phone_number', 'reservations_count', 'is_staff', 'is_active')
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("phone_number", "first_name", "last_name", "email")
    ordering = ("-date_joined",)
    list_editable = ('is_active',)

    fieldsets = (
        ("Credentials", {"fields": ("email", "password")}),
        ("Personal Information", {"fields": ("first_name", "last_name", "phone_number", "date_of_birth")}),
        (
            "Access Control",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Statistics & Dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "phone_number", "usable_password", "password1", "password2"),
            },
        ),
    )

    def full_name_display(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    full_name_display.short_description = 'Full Name'

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _reservations_count=Count('reservations', filter=~Q(reservations__status='deleted'))
        )

    def reservations_count(self, obj):
        count = obj._reservations_count
        if count > 0:
            return format_html('<b>{}</b>', count)
        return count
    reservations_count.short_description = 'Reservations'
    reservations_count.admin_order_field = '_reservations_count'

    # Add a custom detail view title
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        return form
