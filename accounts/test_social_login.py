import json
import re
from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory, override_settings
from django.core import mail
from django.core.cache import cache
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.urls import reverse
from accounts.views import google_login, verify_google_email


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SocialLoginTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.claims = {'uid': 'uid-123', 'email': 'user@example.com', 'email_verified': True,
                       'name': 'Test User', 'firebase': {'sign_in_provider': 'google.com'}}
        verifier = patch('firebase_admin.auth.verify_id_token', return_value=self.claims)
        self.verify = verifier.start()
        self.addCleanup(verifier.stop)
        database = patch('accounts.views.db')
        self.db = database.start()
        self.addCleanup(database.stop)
        self.doc = self.db.collection.return_value.document.return_value
        self.doc.get.return_value.exists = True
        self.doc.get.return_value.to_dict.return_value = {
            'role': 'job_seeker', 'profile_completed': True, 'full_name': 'Test User'}

    def request(self, payload=None, query=''):
        request = self.factory.post('/accounts/google-login/' + query,
                                    json.dumps(payload if payload is not None else {'id_token': 'signed-token'}),
                                    content_type='application/json')
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def complete(self, started, code=None, action=None):
        if code is None and action is None:
            code = re.search(r'code is: (\d{6})', mail.outbox[-1].body).group(1)
        request = self.factory.post(reverse('verify_google_email'),
                                    {'action': action} if action else {'code': code})
        request.session = started.session
        request._messages = FallbackStorage(request)
        return verify_google_email(request)

    def test_google_verifies_token_and_redirects(self):
        request = self.request({'id_token': 'signed-token', 'email': 'forged@example.com'})
        response = google_login(request)
        self.assertEqual(response.status_code, 200)
        self.verify.assert_called_once_with('signed-token', check_revoked=True)
        self.assertNotIn('user_email', request.session)
        self.assertEqual(mail.outbox[-1].to, ['user@example.com'])
        self.assertEqual(json.loads(response.content)['redirect_url'], reverse('verify_google_email'))
        completed = self.complete(request)
        self.assertEqual(request.session['user_email'], 'user@example.com')
        self.assertEqual(completed.url, reverse('jobseeker_dashboard'))

    def test_google_creates_new_account_and_requires_profile_setup(self):
        self.doc.get.return_value.exists = False
        for provider, view in [('google.com', google_login)]:
            with self.subTest(provider=provider):
                self.claims['firebase']['sign_in_provider'] = provider
                request = self.request()
                response = view(request)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(json.loads(response.content)['redirect_url'], reverse('verify_google_email'))
                self.doc.create.assert_not_called()
                self.assertNotIn('user_email', request.session)
                self.assertEqual(self.complete(request).url, reverse('create_profile'))
                saved = self.doc.create.call_args.args[0]
                self.assertEqual(saved['auth_provider'], provider)
                self.assertEqual(saved['first_name'], 'Test')
                self.assertEqual(saved['last_name'], 'User')
                self.assertEqual(saved['firebase_uid'], 'uid-123')
                self.assertFalse(saved['profile_completed'])
                self.assertNotIn('password', saved)

    def test_existing_profile_is_not_replaced_on_social_sign_in(self):
        request = self.request()
        response = google_login(request)
        self.assertEqual(response.status_code, 200)
        self.doc.create.assert_not_called()
        self.doc.update.assert_not_called()
        self.complete(request)
        self.doc.update.assert_called_once_with({'firebase_uid': 'uid-123', 'email_verified': True})

    def test_google_without_email_cannot_create_partial_account(self):
        self.claims.pop('email')
        self.assertEqual(google_login(self.request()).status_code, 400)
        self.db.collection.assert_not_called()

    def test_email_only_payload_is_rejected(self):
        self.assertEqual(google_login(self.request({'email': 'user@example.com'})).status_code, 400)
        self.db.collection.assert_not_called()

    def test_invalid_token_is_rejected(self):
        self.verify.side_effect = ValueError('invalid')
        request = self.request()
        self.assertEqual(google_login(request).status_code, 401)
        self.assertNotIn('user_email', request.session)

    def test_wrong_provider_is_rejected(self):
        self.claims['firebase']['sign_in_provider'] = 'facebook.com'
        self.assertEqual(google_login(self.request()).status_code, 401)

    def test_new_employer_uses_accounts_setup(self):
        self.doc.get.return_value.exists = False
        request = self.request(query='?role=employer')
        response = google_login(request)
        self.assertEqual(json.loads(response.content)['redirect_url'], reverse('verify_google_email'))
        self.assertEqual(self.complete(request).url, reverse('create_profile'))
        self.assertEqual(request.session['user_role'], 'employer')
        self.assertFalse(self.doc.create.call_args.args[0]['verified'])

    def test_admin_registration_is_rejected(self):
        self.doc.get.return_value.exists = False
        self.assertEqual(google_login(self.request(query='?role=admin')).status_code, 400)
        self.doc.create.assert_not_called()

    def test_unverified_email_cannot_claim_existing_account(self):
        self.claims['email_verified'] = False
        self.assertEqual(google_login(self.request()).status_code, 403)

    def test_uid_mismatch_is_rejected(self):
        self.doc.get.return_value.to_dict.return_value['firebase_uid'] = 'different-uid'
        self.assertEqual(google_login(self.request()).status_code, 403)

    def test_login_templates_offer_google_only(self):
        for url in [reverse('login'), reverse('register')]:
            response = self.client.get(url)
            self.assertContains(response, 'data-social-provider="google"')
            self.assertNotContains(response, 'data-social-provider="facebook"')
            self.assertNotContains(response, 'FacebookAuthProvider')
            self.assertContains(response, 'result.user.getIdToken()')
            self.assertEqual(response['Cross-Origin-Opener-Policy'], 'same-origin-allow-popups')
            self.assertContains(response, 'Continue with Google in this tab')

    def test_popup_policy_does_not_change_other_pages(self):
        for path in ['/', reverse('admin_login')]:
            self.assertEqual(self.client.get(path)['Cross-Origin-Opener-Policy'], 'same-origin')

    def test_facebook_endpoint_removed(self):
        self.assertEqual(self.client.get('/accounts/facebook-login/').status_code, 404)

    def test_wrong_code_does_not_sign_in_or_create_account(self):
        self.doc.get.return_value.exists = False
        request = self.request()
        google_login(request)
        code = re.search(r'code is: (\d{6})', mail.outbox[-1].body).group(1)
        wrong = '000000' if code != '000000' else '111111'
        response = self.complete(request, code=wrong)
        self.assertContains(response, 'Incorrect code', status_code=400)
        self.assertNotIn('user_email', request.session)
        self.doc.create.assert_not_called()

    def test_code_locks_after_five_attempts(self):
        request = self.request()
        google_login(request)
        for _ in range(5):
            response = self.complete(request, code='wrong')
        self.assertEqual(response.status_code, 429)
        self.assertNotIn('user_email', request.session)

    def test_code_is_one_time_and_not_stored_in_session(self):
        request = self.request()
        google_login(request)
        token = request.session['google_email_challenge']
        code = re.search(r'code is: (\d{6})', mail.outbox[-1].body).group(1)
        self.assertNotIn(code, str(dict(request.session)))
        self.assertNotIn(code, str(cache.get('email-auth:challenge:' + token)))
        self.complete(request, code=code)
        from accounts.email_auth import consume, EmailAuthError
        with self.assertRaises(EmailAuthError):
            consume(token, code)

    def test_expired_code_cannot_sign_in(self):
        request = self.request()
        google_login(request)
        cache.delete('email-auth:challenge:' + request.session['google_email_challenge'])
        self.assertEqual(self.complete(request, code='123456').url, reverse('login'))
        self.assertNotIn('user_email', request.session)

    def test_resend_is_rate_limited(self):
        request = self.request()
        google_login(request)
        self.assertEqual(self.complete(request, action='resend').status_code, 429)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_invalidates_previous_code(self):
        with patch('accounts.email_auth.secrets.randbelow', side_effect=[123456, 654321]):
            request = self.request()
            google_login(request)
            import hashlib
            identity = hashlib.sha256(b'user@example.com').hexdigest()
            cache.delete('email-auth:cooldown:' + identity)
            self.assertEqual(self.complete(request, action='resend').status_code, 302)
            self.assertEqual(self.complete(request, code='123456').status_code, 400)
            self.assertEqual(self.complete(request, code='654321').url, reverse('jobseeker_dashboard'))

    def test_email_verification_required_for_new_browser(self):
        request = self.request()
        google_login(request)
        other = self.request()
        self.assertEqual(self.complete(other, code='123456').url, reverse('login'))
        self.assertNotIn('user_email', other.session)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
                       EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD='')
    def test_unconfigured_email_does_not_report_success(self):
        request = self.request()
        response = google_login(request)
        self.assertEqual(response.status_code, 503)
        self.assertIn('not configured', json.loads(response.content)['message'])
        self.assertNotIn('user_email', request.session)
        self.assertNotIn('google_email_challenge', request.session)

    @patch('accounts.email_auth.send_mail', side_effect=OSError('unavailable'))
    def test_mail_failure_does_not_create_account(self, send):
        self.doc.get.return_value.exists = False
        request = self.request()
        response = google_login(request)
        self.assertEqual(response.status_code, 503)
        self.doc.create.assert_not_called()
        self.assertNotIn('user_email', request.session)
