from django.core.management.base import BaseCommand, CommandError
from accounts.google_oauth import load_config, validate_config, OAuthError

class Command(BaseCommand):
    help = 'Validate saved Google OAuth client configuration without displaying secrets.'

    def handle(self, *args, **options):
        try:
            validate_config(load_config())
        except OAuthError as error:
            raise CommandError(str(error)) from None
        except Exception:
            raise CommandError('Unable to read Google OAuth configuration.') from None
        self.stdout.write(self.style.SUCCESS('Google OAuth configuration is present. Complete browser sign-in to verify it with Google.'))
