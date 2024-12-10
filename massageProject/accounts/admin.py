from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

UserModel = get_user_model()

@admin.register(UserModel)
class AppUserAdmin(UserAdmin):
    list_display = ('phone_number', 'email')

    fieldsets = (
        (None, {"fields": ("phone_number", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("phone_number", "first_name", "last_name", "email")
    ordering = ("id",)


