from unittest.mock import Mock, patch
from django.test import SimpleTestCase, RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.urls import reverse
from accounts.decorators import role_required


class AdminAccessTests(SimpleTestCase):
    def request(self, role='employer', superuser=False):
        request = RequestFactory().get('/portal-admin/')
        request.session = {'user_role': role, 'user_email': 'example@example.com'}
        request.user = Mock(is_authenticated=True, is_active=True, is_superuser=superuser)
        return request

    def test_public_roles_and_forged_admin_session_are_denied(self):
        for role in ('employer', 'job_seeker', 'admin'):
            view = Mock()
            response = role_required(['admin'])(view)(self.request(role))
            self.assertEqual(response.url, reverse('admin_login'))
            view.assert_not_called()

    def test_superuser_can_access_portal(self):
        view = Mock(return_value=HttpResponse('admin'))
        self.assertEqual(role_required(['admin'])(view)(self.request('admin', True)).status_code, 200)
        view.assert_called_once()

    def test_inactive_superuser_is_denied(self):
        request = self.request('admin', True)
        request.user.is_active = False
        self.assertEqual(role_required(['admin'])(Mock())(request).url, reverse('admin_login'))

    def test_legacy_admin_url_redirects_to_protected_portal(self):
        response = self.client.get('/dashboard/admin/', follow=True)
        self.assertContains(response, 'Private Administrator Access')
        self.assertNotContains(response, 'Administration overview')

    def test_old_shared_credentials_no_longer_work(self):
        with patch('accounts.views.authenticate', return_value=None) as authenticate:
            response = self.client.post(reverse('admin_login'), {'username': 'admin', 'password': 'servinn2026'})
        self.assertContains(response, 'Invalid administrator credentials.')
        self.assertNotIn('user_role', response.wsgi_request.session)
        authenticate.assert_called_once()

    @patch('admin_panel.views.db')
    def test_manage_users_template(self, db):
        from admin_panel.views import manage_users
        doc = Mock(id='seeker@example.com')
        doc.to_dict.return_value = {'role': 'job_seeker', 'full_name': 'Test Seeker'}
        db.collection.return_value.stream.return_value = [doc]
        response = manage_users(self.request('admin', True))
        self.assertContains(response, 'Test Seeker')
        self.assertContains(response, 'Save decision')

