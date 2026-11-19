from unittest.mock import Mock
from django.test import SimpleTestCase, RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpResponse
from django.urls import reverse
from accounts.decorators import role_required


class RoleAccessTests(SimpleTestCase):
    def request(self, role):
        request = RequestFactory().get('/employer/applicants/')
        request.session = {'user_email': 'user@example.com', 'user_role': role} if role else {}
        request._messages = FallbackStorage(request)
        return request

    def test_employer_can_open_applicants(self):
        view = Mock(return_value=HttpResponse('Applicants'))
        response = role_required(['employer'])(view)(self.request('employer'))
        self.assertEqual(response.status_code, 200)
        view.assert_called_once()

    def test_job_seeker_returns_to_own_dashboard(self):
        view = Mock()
        response = role_required(['employer'])(view)(self.request('job_seeker'))
        self.assertEqual(response.url, reverse('jobseeker_dashboard'))
        view.assert_not_called()

    def test_employer_cannot_open_job_seeker_page(self):
        view = Mock()
        response = role_required(['job_seeker'])(view)(self.request('employer'))
        self.assertEqual(response.url, reverse('employer_dashboard'))
        view.assert_not_called()

    def test_expired_session_goes_to_login(self):
        view = Mock()
        response = role_required(['employer'])(view)(self.request(None))
        self.assertEqual(response.url, reverse('login'))
        view.assert_not_called()
