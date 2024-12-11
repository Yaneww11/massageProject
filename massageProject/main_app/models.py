from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

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
    working_hours = models.TextField()

class MessageStudio(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    main_image = models.ImageField(upload_to='studios/')
    address = models.CharField(max_length=255)

class MessageReservation(models.Model):
    massage = models.ForeignKey(
        Massage,
        on_delete=models.CASCADE,
        related_name='reservations'
    )

    masseur = models.ForeignKey(
        'Masseur',
        on_delete=models.CASCADE,
        related_name='reservations',
        blank=True,
    )

    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='reservations',
        blank=True,
    )

    time = models.TimeField()
    date = models.DateField()
    updated_at = models.DateTimeField(auto_now=True)
    additional_text = models.TextField(default='', blank=True)

@receiver(pre_save, sender=MessageReservation)
def set_masseur(sender, instance, **kwargs):
    instance.masseur = Masseur.objects.first()

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

class Comment(models.Model):
    author = models.CharField(
        max_length=30,
    )

    content = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )



