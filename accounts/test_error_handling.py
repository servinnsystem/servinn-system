import json
from unittest.mock import Mock
from django.test import SimpleTestCase, RequestFactory
from django.http import Http404, HttpResponse
from django.core.exceptions import PermissionDenied
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib import messages
from django.template.loader import render_to_string
from django.db import OperationalError
from accounts.middleware import FriendlyErrorMiddleware


class FriendlyErrorTests(SimpleTestCase):
    def request(self, json_request=False):
        request = RequestFactory().post('/employer/post-job/', '{}', content_type='application/json') if json_request else RequestFactory().get('/employer/post-job/')
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_unexpected_error_returns_safe_html_popup_instead_of_traceback(self):
        middleware = FriendlyErrorMiddleware(Mock())
        request = self.request()
        response = middleware.process_exception(request, OperationalError('SECRET_DATABASE_PASSWORD'))
        self.assertContains(response, 'servinn-error-dialog', status_code=503)
        self.assertNotContains(response, 'SECRET_DATABASE_PASSWORD', status_code=503)
        self.assertIn('no-store', response['Cache-Control'])

    def test_unexpected_json_error_keeps_json_contract(self):
        response = FriendlyErrorMiddleware(Mock()).process_exception(self.request(True), RuntimeError('private implementation detail'))
        self.assertEqual(response.status_code, 503)
        self.assertIn('message', json.loads(response.content))
        self.assertNotIn('private implementation detail', response.content.decode())

    def test_http404_and_permission_exceptions_keep_standard_handling(self):
        middleware = FriendlyErrorMiddleware(Mock())
        for error in (Http404(), PermissionDenied()):
            self.assertIsNone(middleware.process_exception(self.request(), error))

    def test_csrf_failure_is_recoverable_and_keeps_status(self):
        middleware = FriendlyErrorMiddleware(Mock(return_value=HttpResponse('CSRF verification failed', status=403)))
        response = middleware(self.request())
        self.assertContains(response, 'servinn-error-dialog', status_code=403)
        self.assertContains(response, 'security token', status_code=403)

    def test_external_referrer_cannot_be_used_as_recovery_link(self):
        request = self.request()
        request.META['HTTP_REFERER'] = 'https://attacker.example/'
        response = FriendlyErrorMiddleware.error_response(request, 503)
        self.assertNotContains(response, 'attacker.example', status_code=503)
        self.assertContains(response, 'href="/"', status_code=503)

    def test_messages_are_available_to_popup_after_inline_render(self):
        request = self.request()
        messages.error(request, 'Please correct your email address.')
        list(messages.get_messages(request))
        html = render_to_string('includes/error_popup.html', request=request)
        self.assertIn('Please correct your email address.', html)
        self.assertIn('aria-labelledby="servinn-error-title"', html)

    def test_message_content_is_escaped(self):
        request = self.request()
        messages.error(request, '<script>alert(1)</script>')
        html = render_to_string('includes/error_popup.html', request=request)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_normal_response_is_unchanged(self):
        expected = HttpResponse('Saved successfully')
        self.assertIs(FriendlyErrorMiddleware(Mock(return_value=expected))(self.request()), expected)

    def test_missing_page_keeps_404_with_popup_and_static_errors_are_not_rewritten(self):
        original = HttpResponse('Not found', status=404)
        middleware = FriendlyErrorMiddleware(Mock(return_value=original))
        response = middleware(self.request())
        self.assertContains(response, 'servinn-error-dialog', status_code=404)
        request = RequestFactory().get('/static/missing.png')
        self.assertIs(middleware(request), original)
