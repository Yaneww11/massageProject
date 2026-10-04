from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from massageProject.main_app.models import BusinessInfo


class BusinessInfoJsonFieldsTest(TestCase):
    def test_new_fields_default_empty(self):
        info = BusinessInfo.objects.create(description="Test Studio")
        self.assertEqual(info.stats, {})
        self.assertEqual(info.credentials, {})
        self.assertEqual(info.faq, [])

    def test_fields_round_trip(self):
        info = BusinessInfo.objects.create(
            description="Test Studio",
            stats={"years_of_practice": "8+", "clients_served": "500+"},
            credentials={"training": [{"title": "Swedish Massage", "subtitle": "Vienna Institute", "year": "2019", "description": "..."}], "recognition": []},
            faq=[{"question": "Do you take walk-ins?", "answer": "No, by appointment only."}],
        )
        info.refresh_from_db()
        self.assertEqual(info.stats["years_of_practice"], "8+")
        self.assertEqual(info.credentials["training"][0]["title"], "Swedish Massage")
        self.assertEqual(info.faq[0]["question"], "Do you take walk-ins?")


class AboutPageContextTest(TestCase):
    def setUp(self):
        dummy_image = SimpleUploadedFile(name='studio.jpg', content=b'', content_type='image/jpeg')
        BusinessInfo.objects.create(description="Reneta's studio.", main_image=dummy_image)

    def test_about_page_has_no_specialist_context(self):
        response = self.client.get(reverse('about_page'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('specialist', response.context)

    def test_about_page_business_info_is_full_instance(self):
        response = self.client.get(reverse('about_page'))
        self.assertIsInstance(response.context['business_info'], BusinessInfo)
        self.assertEqual(response.context['business_info'].description, "Reneta's studio.")


class HeaderNavTest(TestCase):
    def test_nav_has_six_links_in_order(self):
        response = self.client.get(reverse('index'))
        content = response.content.decode()
        # Use reverse to get the correct URL with language prefix
        about_url = reverse('about_page')
        reviews_url = reverse('about_page') + '#reviews'
        about_pos = content.find(f'href="{about_url}"')
        reviews_pos = content.find(f'href="{reviews_url}"')
        self.assertGreater(about_pos, 0)
        self.assertGreater(reviews_pos, about_pos)

    def test_about_page_has_reviews_anchor(self):
        BusinessInfo.objects.create(description="Studio")
        response = self.client.get(reverse('about_page'))
        self.assertContains(response, 'id="reviews"')


class AboutPageHeroInfoTest(TestCase):
    def setUp(self):
        dummy_image = SimpleUploadedFile(name='studio.jpg', content=b'', content_type='image/jpeg')
        self.info = BusinessInfo.objects.create(
            description="Реновирано студио с лично отношение.",
            main_image=dummy_image,
        )

    def test_hero_heading_and_subtitle_render(self):
        response = self.client.get(reverse('about_page'))
        self.assertContains(response, "Историята зад студиото")
        self.assertContains(response, "Лична практика, изградена върху обучение")

    def test_info_section_shows_only_business_info_description(self):
        response = self.client.get(reverse('about_page'))
        self.assertContains(response, "Реновирано студио с лично отношение.")
        self.assertNotContains(response, "specialist")  # sanity: no leftover specialist markup/var name leaks


class AboutPageStatsTest(TestCase):
    def test_all_four_stats_render(self):
        BusinessInfo.objects.create(
            description="Studio",
            stats={
                "years_of_practice": "8+",
                "clients_served": "500+",
                "average_rating": "4.9",
                "certifications_count": "12+",
            },
        )
        response = self.client.get(reverse('about_page'))
        self.assertContains(response, "8+")
        self.assertContains(response, "500+")
        self.assertContains(response, "4.9")
        self.assertContains(response, "12+")

    def test_missing_single_stat_hides_only_that_card(self):
        BusinessInfo.objects.create(
            description="Studio",
            stats={"years_of_practice": "8+", "clients_served": "500+"},
        )
        response = self.client.get(reverse('about_page'))
        self.assertContains(response, "8+")
        self.assertContains(response, "500+")
        self.assertNotContains(response, 'class="stat-card"><div class="stat-value">4.9')

    def test_empty_stats_hides_whole_section(self):
        BusinessInfo.objects.create(description="Studio", stats={})
        response = self.client.get(reverse('about_page'))
        self.assertNotContains(response, 'class="about-stats"')


class AboutPageCredentialsTest(TestCase):
    def test_both_groups_render(self):
        BusinessInfo.objects.create(
            description="Studio",
            credentials_bg={
                "training": [{"title": "Swedish Massage", "subtitle": "Vienna Institute", "year": "2019", "description": "Foundational technique training."}],
                "recognition": [{"title": "Best Wellness Studio", "subtitle": "City Awards", "year": "2023", "description": "Voted by readers."}],
            },
        )
        response = self.client.get(reverse('about_page'))
        self.assertContains(response, "Swedish Massage")
        self.assertContains(response, "Best Wellness Studio")

    def test_only_training_present_hides_recognition_group(self):
        BusinessInfo.objects.create(
            description="Studio",
            credentials_bg={
                "training": [{"title": "Swedish Massage", "subtitle": "Vienna Institute", "year": "2019", "description": "..."}],
                "recognition": [],
            },
        )
        response = self.client.get(reverse('about_page'))
        self.assertContains(response, "Swedish Massage")
        self.assertNotContains(response, 'class="credentials-group credentials-group--recognition"')

    def test_empty_credentials_hides_whole_section(self):
        BusinessInfo.objects.create(description="Studio", credentials_bg={})
        response = self.client.get(reverse('about_page'))
        self.assertNotContains(response, 'class="about-credentials"')


class AboutPageFaqTest(TestCase):
    def test_faq_entries_render(self):
        BusinessInfo.objects.create(
            description="Studio",
            faq_bg=[
                {"question": "Приемате ли без резервация?", "answer": "Не, само с предварителен час."},
                {"question": "Какво да очаквам на първата сесия?", "answer": "Кратък разговор преди началото на масажа."},
            ],
        )
        response = self.client.get(reverse('about_page'))
        self.assertContains(response, "Приемате ли без резервация?")
        self.assertContains(response, "Какво да очаквам на първата сесия?")

    def test_empty_faq_hides_section(self):
        BusinessInfo.objects.create(description="Studio", faq_bg=[])
        response = self.client.get(reverse('about_page'))
        self.assertNotContains(response, 'class="about-faq"')


class AboutPageEnglishLocaleTest(TestCase):
    def test_hero_renders_in_english(self):
        BusinessInfo.objects.create(description="Studio")
        with override_settings(LANGUAGE_CODE='en'):
            response = self.client.get(reverse('about_page'), HTTP_ACCEPT_LANGUAGE='en')
        self.assertContains(response, "The story behind the studio")


class BusinessInfoDescriptionLengthTest(TestCase):
    def test_short_description_is_not_long(self):
        info = BusinessInfo.objects.create(description="A short bio.")
        self.assertFalse(info.is_description_long)

    def test_long_description_is_long(self):
        info = BusinessInfo.objects.create(description="Word " * 200)
        self.assertTrue(info.is_description_long)

    def test_html_tags_are_stripped_before_counting(self):
        padded_markup = "<div><p><strong>Hi</strong></p></div>" * 30
        info = BusinessInfo.objects.create(description=padded_markup)
        self.assertFalse(info.is_description_long)


class AboutPageDescriptionLayoutTest(TestCase):
    def test_short_description_has_no_long_class(self):
        BusinessInfo.objects.create(description="A short bio.")
        response = self.client.get(reverse('about_page'))
        self.assertNotContains(response, "is-long-description")

    def test_long_description_gets_long_class(self):
        BusinessInfo.objects.create(description="Word " * 200)
        response = self.client.get(reverse('about_page'))
        self.assertContains(response, "is-long-description")
