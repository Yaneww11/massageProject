from django.db import models

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

class MessageReservation(models.Model):
    massage = models.ForeignKey(
        Massage,
        on_delete=models.CASCADE,
        related_name='reservations'
    )

    masseur = models.ForeignKey(
        'Masseur',
        on_delete=models.CASCADE,
        related_name='reservations'
    )
    hour = models.TimeField()
    day = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

