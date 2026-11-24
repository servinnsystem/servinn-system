from django.core.management.base import BaseCommand, CommandError
from servinn_core.firestore_config import db
from accounts.database_errors import database_error_message

class Command(BaseCommand):
    help = 'Check Cloud Firestore connectivity without displaying or changing records.'

    def handle(self, *args, **options):
        try:
            next(iter(db.collection('users').limit(1).stream(timeout=10, retry=None)), None)
        except Exception as error:
            raise CommandError(database_error_message(error)) from None
        self.stdout.write(self.style.SUCCESS('Cloud Firestore connection is ready. No records were changed.'))
