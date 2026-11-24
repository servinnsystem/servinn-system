import hashlib
import re
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock, patch
from django.test import SimpleTestCase, RequestFactory, override_settings
from django.core import mail
from django.core.cache import cache
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.urls import reverse
from accounts.views import google_login, google_callback, verify_google_email


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', SERVINN_OAUTH_IGNORE_SAVED=True,
                   GOOGLE_OAUTH_CLIENT_ID='test.apps.googleusercontent.com', GOOGLE_OAUTH_CLIENT_SECRET='test-secret',
                   GOOGLE_OAUTH_REDIRECT_URI='http://127.0.0.1:8000/accounts/google-callback/')
class SocialLoginTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.claims = {'sub': 'google-subject', 'email': 'user@example.com', 'email_verified': True,
                       'name': 'Test User', 'aud': 'test.apps.googleusercontent.com', 'iss': 'https://accounts.google.com'}
        for target, attribute, options in (
            ('accounts.google_oauth.id_token.verify_oauth2_token', 'verify', {'return_value': self.claims}),
            ('accounts.google_oauth.requests.post', 'post', {}),
            ('accounts.views.db', 'db', {})):
            patcher = patch(target, **options)
            setattr(self, attribute, patcher.start())
            self.addCleanup(patcher.stop)
        self.post.return_value.json.return_value = {'id_token': 'signed-google-id-token'}
        self.doc = self.db.collection.return_value.document.return_value
        self.doc.get.return_value.exists = True
        self.doc.get.return_value.to_dict.return_value = {'role': 'job_seeker', 'profile_completed': True, 'full_name': 'Test User'}

    def attach(self, request, session=None):
        request.session = SessionStore() if session is None else session
        request._messages = FallbackStorage(request)
        return request

    def begin(self, role='job_seeker'):
        start = self.attach(self.factory.get('/accounts/google-login/', {'role': role}, HTTP_HOST='127.0.0.1:8000'))
        response = google_login(start)
        return start, response

    def callback_request(self, role='job_seeker'):
        start, _ = self.begin(role)
        flow = start.session['google_oauth']
        self.claims['nonce'] = flow['nonce']
        return self.attach(self.factory.get('/accounts/google-callback/', {'state': flow['state'], 'code': 'authorization-code'}), start.session)

    def callback(self, role='job_seeker'):
        request = self.callback_request(role)
        return request, google_callback(request)

    def complete(self, started, code=None, action=None):
        if code is None and action is None:
            code = re.search(r'code is: (\d{6})', mail.outbox[-1].body).group(1)
        request = self.attach(self.factory.post(reverse('verify_google_email'), {'action': action} if action else {'code': code}), started.session)
        return verify_google_email(request)

    def test_authorization_uses_state_nonce_and_pkce_without_exposing_secret(self):
        request, response = self.begin('employer')
        params = parse_qs(urlsplit(response.url).query)
        self.assertEqual(urlsplit(response.url).netloc, 'accounts.google.com')
        self.assertEqual(params['response_type'], ['code'])
        self.assertEqual(params['code_challenge_method'], ['S256'])
        self.assertEqual(params['scope'], ['openid email profile'])
        self.assertNotIn('test-secret', response.url)
        self.assertEqual(request.session['google_oauth']['role'], 'employer')

    def test_mismatched_host_redirects_before_creating_oauth_state(self):
        request = self.attach(self.factory.get('/accounts/google-login/', {'role': 'employer'}, HTTP_HOST='localhost:8000'))
        response = google_login(request)
        self.assertEqual(response.url, 'http://127.0.0.1:8000/accounts/google-login/?role=employer')
        self.assertNotIn('google_oauth', request.session)
        self.post.assert_not_called()

    def test_google_verifies_token_then_requires_email_code(self):
        request, response = self.callback()
        self.assertEqual(response.url, reverse('verify_google_email'))
        self.assertNotIn('user_email', request.session)
        self.assertEqual(mail.outbox[-1].to, ['user@example.com'])
        self.assertEqual(self.verify.call_args.kwargs['audience'], 'test.apps.googleusercontent.com')
        payload = self.post.call_args.kwargs
        self.assertEqual(payload['timeout'], 15)
        self.assertEqual(payload['data']['grant_type'], 'authorization_code')
        self.assertIn('code_verifier', payload['data'])
        self.assertEqual(self.complete(request).url, reverse('jobseeker_dashboard'))
        self.assertEqual(request.session['user_email'], 'user@example.com')
        self.doc.update.assert_called_once_with({'google_sub': 'google-subject', 'auth_provider': 'google', 'email_verified': True})

    def test_new_employer_created_only_after_code(self):
        self.doc.get.return_value.exists = False
        request, response = self.callback('employer')
        self.doc.create.assert_not_called()
        self.assertNotIn('user_email', request.session)
        self.assertEqual(self.complete(request).url, reverse('create_profile'))
        payload = self.doc.create.call_args.args[0]
        self.assertEqual(payload['role'], 'employer')
        self.assertEqual(payload['google_sub'], 'google-subject')
        self.assertEqual(payload['auth_provider'], 'google')
        self.assertNotIn('password', payload)
        self.assertNotIn('firebase_uid', payload)

    def test_legacy_account_links_only_after_otp_without_changing_role_or_password(self):
        self.doc.get.return_value.to_dict.return_value.update(firebase_uid='old-firebase-uid', password='existing-hash', role='employer')
        request, _ = self.callback('job_seeker')
        self.doc.update.assert_not_called()
        self.assertEqual(self.complete(request).url, reverse('employer_dashboard'))
        changes = self.doc.update.call_args.args[0]
        self.assertNotIn('password', changes)
        self.assertNotIn('role', changes)
        self.assertEqual(changes['google_sub'], 'google-subject')

    def test_wrong_state_expiry_and_replay_never_exchange_code(self):
        for mode in ('state', 'expired'):
            request = self.callback_request()
            if mode == 'state':
                request.GET = request.GET.copy(); request.GET['state'] = 'wrong'
            else:
                flow = request.session['google_oauth']; flow['started'] -= 601; request.session['google_oauth'] = flow
            self.assertEqual(google_callback(request).url, reverse('login'))
        self.post.assert_not_called()
        request = self.callback_request()
        google_callback(request)
        self.post.reset_mock()
        self.assertEqual(google_callback(request).url, reverse('login'))
        self.post.assert_not_called()

    def test_cancelled_google_signin_is_recoverable(self):
        request = self.callback_request()
        request.GET = request.GET.copy(); request.GET['error'] = 'access_denied'
        self.assertEqual(google_callback(request).url, reverse('login'))
        self.post.assert_not_called()
        self.assertTrue(any('cancelled' in str(message) for message in request._messages))

    def test_invalid_identity_claims_do_not_access_database(self):
        for field, value in (('nonce', 'wrong'), ('iss', 'https://attacker.example'), ('aud', 'wrong-client'),
                             ('email_verified', False), ('email', ''), ('sub', '')):
            request = self.callback_request()
            old = self.claims.get(field); self.claims[field] = value
            self.assertEqual(google_callback(request).url, reverse('login'))
            self.claims[field] = old
        self.db.collection.assert_not_called()

    def test_invalid_signature_or_network_failure_does_not_create_session(self):
        self.verify.side_effect = ValueError('private diagnostic')
        request, response = self.callback()
        self.assertEqual(response.url, reverse('login'))
        self.assertNotIn('user_email', request.session)
        self.assertNotIn('private diagnostic', str(list(request._messages)))
        self.doc.create.assert_not_called()

    def test_existing_google_subject_mismatch_or_admin_is_rejected(self):
        for account in ({'role': 'job_seeker', 'google_sub': 'different-subject'}, {'role': 'admin'}):
            self.doc.get.return_value.to_dict.return_value = account
            request, response = self.callback()
            self.assertEqual(response.url, reverse('login'))
        self.doc.update.assert_not_called()

    def test_account_binding_is_rechecked_at_completion(self):
        request, _ = self.callback()
        self.doc.get.return_value.to_dict.return_value['google_sub'] = 'changed-owner'
        self.assertContains(self.complete(request), 'cannot be used', status_code=403)
        self.assertNotIn('user_email', request.session)

    def test_bad_role_and_old_firebase_post_are_rejected(self):
        request, response = self.begin('admin')
        self.assertEqual(response.url, reverse('login'))
        post = self.attach(self.factory.post('/accounts/google-login/', {'id_token': 'old-firebase-token'}))
        self.assertEqual(google_login(post).status_code, 405)
        self.db.collection.assert_not_called()

    def test_templates_use_oauth_links_without_firebase_sdk(self):
        for path in (reverse('login'), reverse('register')):
            response = self.client.get(path)
            self.assertContains(response, 'data-social-provider="google"')
            self.assertContains(response, 'href="/accounts/google-login/"')
            self.assertNotContains(response, 'firebasejs')
            self.assertNotContains(response, 'getIdToken')

    def test_wrong_code_does_not_sign_in(self):
        request, _ = self.callback()
        self.assertContains(self.complete(request, code='wrong'), 'Incorrect code', status_code=400)
        self.assertNotIn('user_email', request.session)

    def test_code_locks_after_five_attempts(self):
        request, _ = self.callback()
        for _ in range(5):
            response = self.complete(request, code='wrong')
        self.assertEqual(response.status_code, 429)
        self.assertNotIn('user_email', request.session)

    def test_code_is_single_use_and_not_stored_plaintext(self):
        request, _ = self.callback()
        token = request.session['google_email_challenge']
        code = re.search(r'code is: (\d{6})', mail.outbox[-1].body).group(1)
        self.assertNotIn(code, str(dict(request.session)))
        self.assertNotIn(code, str(cache.get('email-auth:challenge:' + token)))
        self.complete(request, code)
        from accounts.email_auth import consume, EmailAuthError
        with self.assertRaises(EmailAuthError): consume(token, code)

    def test_expired_code_cannot_sign_in(self):
        request, _ = self.callback()
        cache.delete('email-auth:challenge:' + request.session['google_email_challenge'])
        self.assertEqual(self.complete(request, '123456').url, reverse('login'))

    def test_resend_is_rate_limited(self):
        request, _ = self.callback()
        self.assertEqual(self.complete(request, action='resend').status_code, 429)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_replaces_old_code(self):
        with patch('accounts.email_auth.secrets.randbelow', side_effect=[123456, 654321]):
            request, _ = self.callback()
            cache.delete('email-auth:cooldown:' + hashlib.sha256(b'user@example.com').hexdigest())
            self.assertEqual(self.complete(request, action='resend').status_code, 302)
            self.assertEqual(self.complete(request, '123456').status_code, 400)
            self.assertEqual(self.complete(request, '654321').url, reverse('jobseeker_dashboard'))

    def test_other_browser_cannot_use_pending_code(self):
        request, _ = self.callback()
        unrelated = self.attach(self.factory.post(reverse('verify_google_email'), {'code': '123456'}))
        self.assertEqual(verify_google_email(unrelated).url, reverse('login'))

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD='')
    def test_unconfigured_mail_does_not_sign_in(self):
        request, response = self.callback()
        self.assertEqual(response.url, reverse('login'))
        self.assertNotIn('user_email', request.session)
        self.assertTrue(any('not configured' in str(message) for message in request._messages))

    @patch('accounts.email_auth.send_mail', side_effect=OSError('unavailable'))
    def test_mail_failure_does_not_create_account(self, send):
        self.doc.get.return_value.exists = False
        request, response = self.callback()
        self.assertEqual(response.url, reverse('login'))
        self.doc.create.assert_not_called()
        self.assertNotIn('user_email', request.session)


class GoogleOAuthConfigurationTests(SimpleTestCase):
    def test_credentials_persist_encrypted_without_redisplaying_secret(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from accounts.google_oauth import save_config, load_config
        config = {'client_id': 'test.apps.googleusercontent.com', 'client_secret': 'private-test-client-secret',
                  'redirect_uri': 'http://127.0.0.1:8000/accounts/google-callback/'}
        with TemporaryDirectory() as directory:
            with override_settings(BASE_DIR=Path(directory), SERVINN_OAUTH_IGNORE_SAVED=False):
                save_config(config)
                encrypted = (Path(directory) / '.runtime/google-oauth.enc').read_bytes()
                self.assertNotIn(b'private-test-client-secret', encrypted)
                self.assertEqual(load_config(), config)

    def test_invalid_or_nonlocal_insecure_callback_is_rejected(self):
        from accounts.google_oauth import validate_config, OAuthError
        for callback in ('http://attacker.example/accounts/google-callback/',
                         'https://example.com/wrong-path/',
                         'https://user:password@example.com/accounts/google-callback/',
                         'https://example.com/accounts/google-callback/?next=bad'):
            with self.subTest(callback=callback):
                with self.assertRaises(OAuthError):
                    validate_config({'client_id': 'test.apps.googleusercontent.com', 'client_secret': 'test-secret', 'redirect_uri': callback})
