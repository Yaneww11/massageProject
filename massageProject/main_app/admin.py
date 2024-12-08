from django.contrib import admin

from massageProject.main_app.models import Massage, Image, Gallery, HomePage, GalleryImage, MessageStudio, Masseur


@admin.register(Massage)
class MassageAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_in_minutes')
    search_fields = ('name', 'short_description')
    list_filter = ('home_page','price', 'duration_in_minutes')
    fields = ('name', 'description', 'price', 'duration_in_minutes', 'short_description', 'image', 'home_page')
    ordering = ('name',)

@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ('alt_text',)
    search_fields = ('alt_text',)
    fields = ('image', 'alt_text')

class GalleryImageInline(admin.TabularInline):  # or admin.StackedInline
    model = GalleryImage
    extra = 1

@admin.register(Gallery)
class GalleryAdmin(admin.ModelAdmin):
    inlines = [GalleryImageInline]

@admin.register(HomePage)
class HomePageAdmin(admin.ModelAdmin):
    list_display = ('title',)
    fields = ('title', 'description', 'gallery')

@admin.register(MessageStudio)
class MessageStudiosAdmin(admin.ModelAdmin):
    list_display = ('name',)
    fields = ('name', 'description', 'main_image', 'address')

@admin.register(Masseur)
class MasseurAdmin(admin.ModelAdmin):
    list_display = ('name',)
    fields = ('name', 'description', 'image', 'phone_number', 'email', 'working_hours')
