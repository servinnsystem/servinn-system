"""Provision a missing Django administrator from server-owned environment variables."""
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction


class Command(BaseCommand):
    help = 'Create a missing bootstrap administrator; never reset or promote an existing account.'

    def handle(self, *args, **options):
        username = os.getenv('SERVINN_ADMIN_USERNAME', '').strip()
        email = os.getenv('SERVINN_ADMIN_EMAIL', '').strip()
        password = os.getenv('SERVINN_ADMIN_PASSWORD', '')
        if not any((username, email, password)):
            self.stdout.write('Administrator bootstrap not configured; no accounts changed.')
            return
        if not all((username, email, password)):
            raise CommandError('Set all three SERVINN_ADMIN_USERNAME, SERVINN_ADMIN_EMAIL and SERVINN_ADMIN_PASSWORD variables.')
        User = get_user_model()
        with transaction.atomic():
            existing = User.objects.filter(username=username).first()
            if existing:
                if not (existing.is_active and existing.is_staff and existing.is_superuser):
                    raise CommandError('The bootstrap username belongs to an existing non-administrator or inactive account. No account was changed.')
                self.stdout.write('Administrator already exists; credentials and permissions unchanged.')
                return
            candidate = User(username=username, email=email)
            try:
                candidate.full_clean(exclude=['password'])
                validate_email(email)
                if len(password) < 12:
                    raise ValidationError('Password too short.')
                validate_password(password, user=candidate)
            except ValidationError:
                raise CommandError('Administrator configuration is invalid. Use a valid username and email, and a unique strong password of at least 12 characters.') from None
            User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS('Administrator created securely. Credentials were not printed.'))
