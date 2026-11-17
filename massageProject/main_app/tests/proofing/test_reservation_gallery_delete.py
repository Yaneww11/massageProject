from massageProject.main_app.models import Gallery, Image, Reservation
from massageProject.main_app.tests.proofing.test_marked_photos import MarkedPhotosTestBase


class ReservationGalleryDeleteTest(MarkedPhotosTestBase):
    def test_deleting_gallery_keeps_reservation(self):
        self.gallery.delete()
        self.reservation.refresh_from_db()
        self.assertIsNone(self.reservation.gallery_id)

    def test_deleting_reservation_deletes_gallery(self):
        gallery_pk = self.gallery.pk
        self.reservation.delete()
        self.assertFalse(Gallery.objects.filter(pk=gallery_pk).exists())
        self.assertFalse(Image.objects.filter(gallery_id=gallery_pk).exists())

    def test_cancelling_reservation_keeps_gallery(self):
        self.reservation.change_status(Reservation.STATUS_DELETED)
        self.assertTrue(Gallery.objects.filter(pk=self.gallery.pk).exists())
