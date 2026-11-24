import smtplib

from django.conf import settings
from django.core.mail import get_connection
from accounts.mail_settings import load_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Check SMTP connection and credentials without sending an email.'

    def handle(self, *args, **options):
        if settings.EMAIL_BACKEND == 'accounts.brevo_backend.EmailBackend':
            from accounts.mail_settings import delivery_options
            try:
                delivery_options()
            except ValueError as error:
                raise CommandError(str(error)) from None
            self.stdout.write(self.style.SUCCESS('Brevo HTTPS configuration is present. No email was sent; live delivery is not verified.'))
            return
        if settings.EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend':
            raise CommandError('Select the SMTP email backend to check live email delivery.')
        try:
            config = load_mail()
        except Exception:
            raise CommandError('Saved Gmail settings could not be read. Open Administration > Sign-in settings to configure the sender again.') from None
        if not config.get('sender') or not config.get('password'):
            raise CommandError('Gmail sender credentials are missing. Open Administration > Sign-in settings to configure the sender.')
        try:
            with get_connection(username=config['sender'], password=config['password']) as connection:
                if connection.connection is None:
                    raise CommandError('The SMTP connection could not be opened.')
        except smtplib.SMTPAuthenticationError:
            raise CommandError('Gmail rejected the login. Use a Gmail App Password for the sender address, with 2-Step Verification enabled.')
        except (smtplib.SMTPException, OSError):
            raise CommandError('Unable to connect to the email server. Check your internet connection, SMTP host, port, and TLS settings.')
        self.stdout.write(self.style.SUCCESS('SMTP login succeeded. No email was sent.'))
