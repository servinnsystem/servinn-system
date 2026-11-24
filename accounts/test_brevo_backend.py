from unittest.mock import Mock, patch
import requests
from django.core.mail import send_mail
from django.test import SimpleTestCase, override_settings
from accounts.mail_settings import delivery_options


@override_settings(EMAIL_BACKEND='accounts.brevo_backend.EmailBackend',
                   BREVO_API_KEY='test-private-key', DEFAULT_FROM_EMAIL='sender@example.com')
class BrevoBackendTests(SimpleTestCase):
    @patch('accounts.brevo_backend.requests.post')
    def test_message_uses_https_and_verified_sender_without_smtp(self, post):
        post.return_value = Mock(status_code=201, json=lambda: {'messageId': 'accepted'})
        self.assertEqual(send_mail('Verification', 'Code: 123456', None,
                                   ['applicant@gmail.com'], **delivery_options()), 1)
        args, options = post.call_args
        self.assertEqual(args[0], 'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(options['headers']['api-key'], 'test-private-key')
        self.assertEqual(options['json']['sender']['email'], 'sender@example.com')
        self.assertEqual(options['json']['to'], [{'email': 'applicant@gmail.com'}])
        self.assertEqual(options['json']['textContent'], 'Code: 123456')
        self.assertFalse(options['allow_redirects'])
        self.assertEqual(options['timeout'], 15)

    @override_settings(BREVO_API_KEY='')
    @patch('accounts.brevo_backend.requests.post')
    def test_missing_key_prevents_network_access(self, post):
        with self.assertRaises(ValueError):
            delivery_options()
        self.assertEqual(send_mail('Test', 'Body', None, ['applicant@gmail.com'], fail_silently=True), 0)
        post.assert_not_called()

    @patch('accounts.brevo_backend.requests.post')
    def test_rejection_is_safe_and_not_counted_as_sent(self, post):
        post.return_value = Mock(status_code=401, text='test-private-key private body')
        with self.assertRaises(RuntimeError) as error:
            send_mail('Test', 'Body', None, ['applicant@gmail.com'])
        self.assertNotIn('test-private-key', str(error.exception))
        self.assertEqual(send_mail('Test', 'Body', None, ['applicant@gmail.com'], fail_silently=True), 0)

    @patch('accounts.brevo_backend.requests.post', side_effect=requests.Timeout('private details'))
    def test_timeout_is_safe(self, post):
        with self.assertRaisesMessage(RuntimeError, 'HTTPS email delivery failed'):
            send_mail('Test', 'Body', None, ['applicant@gmail.com'])
        self.assertEqual(post.call_count, 1)
