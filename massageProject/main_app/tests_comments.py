from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from massageProject.main_app.models import Comment, Specialist, BusinessInfo
from massageProject.accounts.models import CustomUser

class CommentLogicTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            phone_number='0888888888',
            email='test@example.com',
            password='password123',
            first_name='John',
            last_name='Doe'
        )
        # AboutPage needs a Specialist and BusinessInfo to render
        dummy_image = SimpleUploadedFile(name='test_image.jpg', content=b'', content_type='image/jpeg')
        Specialist.objects.create(name="Test Specialist", image=dummy_image)
        BusinessInfo.objects.create(description="Test Studio")

        # Create some reviewed and unreviewed comments
        for i in range(20):
            Comment.objects.create(
                author=f"Author {i}",
                content=f"Content {i}",
                is_reviewed=(i % 2 == 0) # 0, 2, 4 ... are reviewed (10 comments)
            )

    def test_about_page_shows_only_reviewed_comments(self):
        response = self.client.get(reverse('about_page'))
        self.assertEqual(response.status_code, 200)
        comments = response.context['comments']
        self.assertEqual(len(comments), 10) # All 10 reviewed comments
        for comment in comments:
            self.assertTrue(comment.is_reviewed)

    def test_about_page_limit_15(self):
        # Create more reviewed comments to exceed 15
        for i in range(20, 40):
            Comment.objects.create(
                author=f"Author {i}",
                content=f"Content {i}",
                is_reviewed=True
            )
        
        # Total reviewed: 10 (from setUp) + 20 = 30
        response = self.client.get(reverse('about_page'))
        comments = response.context['comments']
        self.assertEqual(len(comments), 15)
        self.assertEqual(response.context['total_comments_count'], 30)

    def test_all_comments_view_pagination(self):
        # 10 reviewed comments from setUp
        response = self.client.get(reverse('all_comments'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['comments']), 10)

        # Add more to trigger pagination
        for i in range(20, 50):
            Comment.objects.create(
                author=f"Author {i}",
                content=f"Content {i}",
                is_reviewed=True
            )
        # Total reviewed: 10 + 30 = 40
        # paginate_by = 15
        
        response = self.client.get(reverse('all_comments'))
        self.assertEqual(len(response.context['comments']), 15)
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(response.context['paginator'].num_pages, 3) # 15 + 15 + 10 = 40

    def test_comment_submission_is_not_immediately_visible(self):
        self.client.login(email='test@example.com', password='password123')
        response = self.client.post(reverse('about_page'), {'content': 'New pending comment'})
        self.assertEqual(response.status_code, 302) # Redirects
        
        # Check database
        new_comment = Comment.objects.get(content='New pending comment')
        self.assertFalse(new_comment.is_reviewed)
        
        # Check AboutPage again
        response = self.client.get(reverse('about_page'))
        self.assertNotIn('New pending comment', response.content.decode())
