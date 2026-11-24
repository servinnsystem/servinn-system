from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from accounts.views import register_seeker, register_employer
from accounts.database_errors import database_error_message
from django.db import OperationalError


class DatabaseRegistrationErrorTests(SimpleTestCase):
    def test_database_failure_message_is_safe(self):
        self.assertIn('Cloud Firestore connection settings', database_error_message(OperationalError('private diagnostic')))

    @patch('accounts.views.db')
    def test_both_registration_forms_show_safe_credential_error(self, db):
        ref = db.collection.return_value.document.return_value
        ref.create.side_effect = OperationalError('private-diagnostic')
        for view in (register_seeker, register_employer):
            request = RequestFactory().post('/', {'email': 'new@example.com', 'password': 'private-test-password'})
            request.session = {}
            request._messages = FallbackStorage(request)
            with self.assertLogs('accounts.database_errors', level='ERROR') as log:
                response = view(request)
            self.assertContains(response, 'Cloud Firestore connection settings', status_code=503)
            self.assertNotContains(response, 'private-diagnostic', status_code=503)
            self.assertNotContains(response, 'private-test-password', status_code=503)
            self.assertNotIn('private-diagnostic', str(log.output))
            self.assertNotIn('private-test-password', str(log.output))
        ref.set.assert_not_called()
        ref.update.assert_not_called()
