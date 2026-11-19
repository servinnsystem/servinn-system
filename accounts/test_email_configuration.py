import smtplib
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, override_settings


@override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
                   EMAIL_HOST_USER='sender@gmail.com', EMAIL_HOST_PASSWORD='test-only-secret')
class EmailConfigurationTests(SimpleTestCase):
    @override_settings(EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD='')
    @patch('accounts.management.commands.check_email.get_connection')
    def test_missing_credentials_do_not_connect(self, connection):
        with self.assertRaisesMessage(CommandError, 'run_with_gmail.ps1'):
            call_command('check_email', stdout=StringIO())
        connection.assert_not_called()

    @patch('accounts.management.commands.check_email.get_connection')
    def test_checks_connection_without_sending_mail(self, connection):
        output = StringIO()
        call_command('check_email', stdout=output)
        self.assertIn('SMTP login succeeded. No email was sent.', output.getvalue())
        connection.return_value.__enter__.assert_called_once()
        connection.return_value.__enter__.return_value.send_messages.assert_not_called()

    @patch('accounts.management.commands.check_email.get_connection')
    def test_login_rejection_is_explained_without_exposing_secrets(self, connection):
        connection.return_value.__enter__.side_effect = smtplib.SMTPAuthenticationError(535, b'private server response')
        with self.assertRaisesMessage(CommandError, 'App Password') as error:
            call_command('check_email', stdout=StringIO())
        self.assertNotIn('private server response', str(error.exception))
        self.assertNotIn('test-only-secret', str(error.exception))

    @patch('accounts.management.commands.check_email.get_connection')
    def test_network_failure_is_explained(self, connection):
        connection.return_value.__enter__.side_effect = OSError('network unavailable')
        with self.assertRaisesMessage(CommandError, 'Unable to connect'):
            call_command('check_email', stdout=StringIO())
