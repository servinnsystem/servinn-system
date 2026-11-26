from unittest.mock import Mock, patch
from django.test import SimpleTestCase, RequestFactory
from django.http import Http404
from django.urls import reverse
from admin_panel.views import account_profile


class AccountProfileTests(SimpleTestCase):
    @patch('admin_panel.views.db')
    def test_identity_information_and_private_upload_links_are_available_to_admin(self, db):
        db.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {
            'role': 'job_seeker', 'id_number': 'TEST-ID-123', 'complete_address': 'Sample Street, Iloilo',
            'id_document_back_file': {'path': 'private-back'}, 'selfie_document_file': {'path': 'private-selfie'}}
        response = account_profile(self.request(), 'person@example.com')
        for text in ('Identity verification', 'TEST-ID-123', 'Sample Street, Iloilo',
                     'Download Valid ID (back)', 'Download Selfie holding ID'):
            self.assertContains(response, text)
        for kind in ('id_document_back', 'selfie_document'):
            self.assertContains(response, reverse('profile_file', args=['person@example.com', kind]))
        self.assertNotContains(response, 'private-back')
        self.assertNotContains(response, 'private-selfie')

    def request(self, admin=True):
        request = RequestFactory().get('/')
        request.user = Mock(is_authenticated=True, is_active=True, is_superuser=admin)
        request.session = {'user_role': 'admin'}
        return request

    @patch('admin_panel.views.db')
    def test_profiles_render_only_selected_fields(self, db):
        for role, expected in [('job_seeker', 'Qualifications'), ('employer', 'Company profile')]:
            db.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {
                'role': role, 'full_name': 'Test Person', 'skills': ['Cooking', 'First aid'],
                'description': '<script>alert(1)</script>', 'password': 'DO-NOT-DISPLAY',
            }
            response = account_profile(self.request(), 'phone:+639123456789')
            self.assertContains(response, expected)
            self.assertContains(response, 'Test Person')
            self.assertNotContains(response, 'DO-NOT-DISPLAY')
            self.assertNotContains(response, '<script>alert(1)</script>')
            self.assertEqual(response['Cache-Control'], 'private, no-store')

    @patch('admin_panel.views.db')
    def test_non_admin_denied_before_database_access(self, db):
        response = account_profile(self.request(False), 'person@example.com')
        self.assertEqual(response.url, reverse('admin_login'))
        db.collection.assert_not_called()

    @patch('admin_panel.views.db')
    def test_missing_account(self, db):
        db.collection.return_value.document.return_value.get.return_value.exists = False
        with self.assertRaises(Http404):
            account_profile(self.request(), 'missing@example.com')

    @patch('admin_panel.views.db')
    def test_admin_record_not_exposed(self, db):
        db.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {'role': 'admin'}
        with self.assertRaises(Http404):
            account_profile(self.request(), 'admin@example.com')
