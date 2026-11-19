import smtplib

from django.conf import settings
from django.core.mail import get_connection
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Check SMTP connection and credentials without sending an email.'

    def handle(self, *args, **options):
        if settings.EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend':
            raise CommandError('Select the SMTP email backend to check live email delivery.')
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            raise CommandError(r'Gmail sender credentials are missing. Run .\run_with_gmail.ps1 to configure this server session.')
        try:
            with get_connection() as connection:
                if connection.connection is None:
                    raise CommandError('The SMTP connection could not be opened.')
        except smtplib.SMTPAuthenticationError:
            raise CommandError('Gmail rejected the login. Use a Gmail App Password for the sender address, with 2-Step Verification enabled.')
        except (smtplib.SMTPException, OSError):
            raise CommandError('Unable to connect to the email server. Check your internet connection, SMTP host, port, and TLS settings.')
        self.stdout.write(self.style.SUCCESS('SMTP login succeeded. No email was sent.'))
