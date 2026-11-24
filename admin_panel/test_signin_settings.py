from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from django.test import SimpleTestCase, RequestFactory, override_settings
from django.contrib.messages.storage.fallback import FallbackStorage
from django.urls import reverse
from admin_panel.signin_settings import signin_settings
from accounts.mail_settings import save_mail, load_mail, delivery_options


class SigninSettingsTests(SimpleTestCase):
    def request(self, data=None, admin=True):
        factory = RequestFactory()
        request = factory.get('/') if data is None else factory.post('/', data)
        request.session = {}
        request.user = Mock(is_authenticated=admin, is_active=True, is_superuser=admin)
        request._messages = FallbackStorage(request)
        return request

    @patch('admin_panel.signin_settings.load_mail')
    def test_only_administrators_can_access_sender_settings(self, load):
        response = signin_settings(self.request(admin=False))
        self.assertEqual(response.url, reverse('admin_login'))
        load.assert_not_called()

    @patch('admin_panel.signin_settings.load_mail', return_value={'sender': 'sender@gmail.com', 'password': 'secret-never-rendered'})
    def test_settings_page_never_displays_saved_secret(self, load):
        response = signin_settings(self.request())
        self.assertContains(response, 'Google sign-in settings')
        self.assertContains(response, 'sender@gmail.com')
        self.assertNotContains(response, 'secret-never-rendered')
        self.assertIn('no-store', response['Cache-Control'])

    @patch('admin_panel.signin_settings.save_mail')
    @patch('admin_panel.signin_settings.test_mail', return_value=True)
    @patch('admin_panel.signin_settings.load_mail', return_value={})
    def test_sender_verified_before_save_and_password_not_returned(self, load, check, save):
        response = signin_settings(self.request({'action': 'mail', 'sender': 'sender@gmail.com', 'app_password': 'abcd efgh ijkl mnop'}))
        check.assert_called_once_with('sender@gmail.com', 'abcdefghijklmnop')
        save.assert_called_once_with('sender@gmail.com', 'abcdefghijklmnop')
        self.assertEqual(response.url, reverse('admin_signin_settings'))

    @patch('admin_panel.signin_settings.save_mail')
    @patch('admin_panel.signin_settings.test_mail', side_effect=OSError('private connection detail'))
    @patch('admin_panel.signin_settings.load_mail', return_value={})
    def test_failed_mail_check_does_not_replace_credentials(self, load, check, save):
        response = signin_settings(self.request({'action': 'mail', 'sender': 'sender@gmail.com', 'app_password': 'abcdefghijklmnop'}))
        self.assertContains(response, 'Gmail connection failed')
        self.assertNotContains(response, 'abcdefghijklmnop')
        self.assertNotContains(response, 'private connection detail')
        save.assert_not_called()

    @patch('admin_panel.signin_settings.save_mail')
    @patch('admin_panel.signin_settings.test_mail')
    @patch('admin_panel.signin_settings.load_mail', return_value={'sender': 'old@gmail.com', 'password': 'abcdefghijklmnop'})
    def test_new_sender_requires_new_password(self, load, check, save):
        response = signin_settings(self.request({'action': 'mail', 'sender': 'new@gmail.com', 'app_password': ''}))
        self.assertContains(response, 'Enter an App Password for this sender')
        save.assert_not_called()
        check.assert_not_called()

    def test_sender_persists_encrypted_and_is_used_without_environment_variables(self):
        with TemporaryDirectory() as directory:
            with override_settings(BASE_DIR=Path(directory), SECRET_KEY='test-encryption-key', SERVINN_MAIL_IGNORE_SAVED=False,
                                   EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD=''):
                save_mail('sender@gmail.com', 'abcdefghijklmnop')
                ciphertext = (Path(directory) / '.runtime/mail.enc').read_bytes()
                self.assertNotIn(b'abcdefghijklmnop', ciphertext)
                self.assertNotIn(b'sender@gmail.com', ciphertext)
                self.assertEqual(load_mail()['sender'], 'sender@gmail.com')
                self.assertEqual(delivery_options()['auth_password'], 'abcdefghijklmnop')

    @patch('admin_panel.signin_settings.load_mail', return_value={})
    @patch('accounts.google_oauth.save_config')
    def test_google_secret_not_shown_and_invalid_callback_not_saved(self, save, load):
        request = self.request({'action': 'google', 'client_id': 'invalid-id', 'client_secret': 'private-oauth-secret', 'redirect_uri': 'not-a-url'})
        response = signin_settings(request)
        save.assert_not_called()
        self.assertNotContains(response, 'private-oauth-secret')

    @patch('admin_panel.signin_settings.load_mail', return_value={})
    @patch('accounts.google_oauth.load_config', return_value={'client_id': 'test.apps.googleusercontent.com', 'client_secret': 'saved-oauth-secret', 'redirect_uri': 'http://127.0.0.1:8000/accounts/google-callback/'})
    @patch('accounts.google_oauth.save_config')
    def test_google_secret_kept_for_same_client_without_displaying(self, save, config, mail):
        response = signin_settings(self.request())
        self.assertNotContains(response, 'saved-oauth-secret')
        request = self.request({'action': 'google', 'client_id': 'test.apps.googleusercontent.com', 'client_secret': '', 'redirect_uri': 'http://127.0.0.1:8000/accounts/google-callback/'})
        self.assertEqual(signin_settings(request).url, reverse('admin_signin_settings'))
        self.assertEqual(save.call_args.args[0]['client_secret'], 'saved-oauth-secret')
