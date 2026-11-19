from unittest.mock import patch

from django.contrib.auth.hashers import make_password, check_password
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse
from google.api_core.exceptions import AlreadyExists

from accounts.views import login_view, register_seeker, register_employer
from accounts.passwords import verify_account_password


class PasswordAccountTests(SimpleTestCase):
    def setUp(self):
        # Keep actual password hashing in tests, using a smaller test-only cost.
        hasher = patch('django.contrib.auth.hashers.PBKDF2PasswordHasher.iterations', 1000)
        hasher.start()
        self.addCleanup(hasher.stop)
        database = patch('accounts.views.db')
        self.db = database.start()
        self.addCleanup(database.stop)
        self.document = self.db.collection.return_value.document.return_value

    def request(self, **changes):
        data = {'email': 'test@example.com', 'password': 'test-password'}
        data.update(changes)
        request = RequestFactory().post('/', data)
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_both_registration_types_store_hashes(self):
        for register in (register_seeker, register_employer):
            with self.subTest(register=register.__name__):
                response = register(self.request())
                self.assertEqual(response.url, reverse('login'))
                stored = self.document.create.call_args.args[0]['password']
                self.assertNotEqual(stored, 'test-password')
                self.assertTrue(check_password('test-password', stored))
                self.document.set.assert_not_called()

    def test_existing_email_is_not_overwritten(self):
        self.document.create.side_effect = AlreadyExists('exists')
        for register in (register_seeker, register_employer):
            response = register(self.request())
            self.assertContains(response, 'already exists')
        self.document.set.assert_not_called()
        self.document.update.assert_not_called()

    def test_legacy_password_is_upgraded_after_successful_login(self):
        self.document.get.return_value.to_dict.return_value = {
            'role': 'job_seeker', 'profile_completed': True, 'password': 'test-password'}
        request = self.request()
        response = login_view(request)
        self.assertEqual(response.url, reverse('jobseeker_dashboard'))
        self.assertEqual(request.session['user_email'], 'test@example.com')
        stored = self.document.update.call_args.args[0]['password']
        self.assertTrue(check_password('test-password', stored))

    def test_hashed_password_signs_in(self):
        self.document.get.return_value.to_dict.return_value = {
            'role': 'employer', 'profile_completed': True, 'password': make_password('test-password')}
        self.assertEqual(login_view(self.request()).url, reverse('employer_dashboard'))
        self.document.update.assert_not_called()

    def test_wrong_password_does_not_create_session_or_upgrade(self):
        self.document.get.return_value.to_dict.return_value = {
            'role': 'job_seeker', 'password': 'different-password'}
        request = self.request()
        self.assertContains(login_view(request), 'Invalid email or password.')
        self.assertNotIn('user_email', request.session)
        self.document.update.assert_not_called()

    def test_missing_or_malformed_password_does_not_crash(self):
        for stored in (None, '', 'pbkdf2_sha256$broken'):
            self.assertFalse(verify_account_password('test-password', stored)[0])

    def test_password_hash_cannot_be_used_as_the_password(self):
        stored = make_password('test-password')
        self.assertFalse(verify_account_password(stored, stored)[0])
