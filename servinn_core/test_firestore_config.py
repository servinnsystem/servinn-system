from unittest.mock import Mock, patch
from pathlib import Path
from django.test import SimpleTestCase, override_settings
from servinn_core import firestore_config

class FirestoreConfigTests(SimpleTestCase):
    @override_settings(FIRESTORE_PROJECT_ID='test-project', FIRESTORE_DATABASE_ID='(default)', FIRESTORE_CREDENTIALS_FILE='private-key.json')
    @patch('servinn_core.firestore_config.service_account.Credentials.from_service_account_file')
    @patch('servinn_core.firestore_config.firestore.Client')
    @patch('pathlib.Path.stat')
    def test_native_database_client_is_created_lazily_and_reused(self, stat, client, credential):
        old_client, old_version = firestore_config._client, firestore_config._version
        firestore_config._client = None; firestore_config._version = None
        stat.return_value.st_mtime_ns = 1
        try:
            first = firestore_config.get_client()
            self.assertIs(first, firestore_config.get_client())
            client.assert_called_once()
            self.assertEqual(client.call_args.kwargs['project'], 'test-project')
            self.assertEqual(client.call_args.kwargs['database'], '(default)')
        finally:
            firestore_config._client, firestore_config._version = old_client, old_version

    def test_development_environment_watcher_is_preserved(self):
        from servinn_core.settings import _watch_environment_file, BASE_DIR
        sender = Mock(extra_files=set())
        _watch_environment_file(sender)
        self.assertIn(BASE_DIR / '.env', sender.extra_files)
