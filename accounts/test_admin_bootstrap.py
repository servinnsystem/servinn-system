from io import StringIO
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model, authenticate
from django.core.management import call_command, CommandError


class AdminBootstrapTests(TestCase):
    config = {'SERVINN_ADMIN_USERNAME': 'site-reviewer',
              'SERVINN_ADMIN_EMAIL': 'reviewer@example.com',
              'SERVINN_ADMIN_PASSWORD': 'Sample!Random-Only4Tests-92'}

    def run_command(self, config):
        output = StringIO()
        with patch.dict('os.environ', config, clear=True):
            call_command('ensure_admin', stdout=output)
        return output.getvalue()

    def test_absent_configuration_changes_nothing(self):
        self.run_command({})
        self.assertFalse(get_user_model().objects.exists())

    def test_creates_hashed_password_and_can_sign_in(self):
        output = self.run_command(self.config)
        user = authenticate(username=self.config['SERVINN_ADMIN_USERNAME'], password=self.config['SERVINN_ADMIN_PASSWORD'])
        self.assertIsNotNone(user)
        self.assertTrue(user.is_active and user.is_staff and user.is_superuser)
        self.assertNotEqual(user.password, self.config['SERVINN_ADMIN_PASSWORD'])
        self.assertNotIn(self.config['SERVINN_ADMIN_PASSWORD'], output)
        response = self.client.post('/portal-admin/login/', {'username': user.username, 'password': self.config['SERVINN_ADMIN_PASSWORD']})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session['user_role'], 'admin')

    def test_repeated_bootstrap_does_not_reset_password(self):
        self.run_command(self.config)
        changed = dict(self.config, SERVINN_ADMIN_PASSWORD='Different!Password9-only')
        self.run_command(changed)
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertIsNotNone(authenticate(username=self.config['SERVINN_ADMIN_USERNAME'], password=self.config['SERVINN_ADMIN_PASSWORD']))

    def test_never_promotes_existing_normal_account(self):
        user = get_user_model().objects.create_user(username=self.config['SERVINN_ADMIN_USERNAME'], password='Existing-Password3!')
        with self.assertRaises(CommandError):
            self.run_command(self.config)
        user.refresh_from_db()
        self.assertFalse(user.is_superuser)

    def test_partial_or_weak_configuration_fails_without_printing_password(self):
        for config in [dict(self.config, SERVINN_ADMIN_EMAIL=''), dict(self.config, SERVINN_ADMIN_PASSWORD='short')]:
            with self.assertRaises(CommandError) as error:
                self.run_command(config)
            self.assertNotIn(config['SERVINN_ADMIN_PASSWORD'], str(error.exception))
        self.assertFalse(get_user_model().objects.exists())
