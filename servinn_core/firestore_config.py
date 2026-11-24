"""Lazy Cloud Firestore database client. Authentication remains direct Google OAuth."""
from pathlib import Path
from threading import RLock
from django.conf import settings
from google.oauth2 import service_account
from google.cloud import firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP, ArrayUnion
from google.cloud.firestore_v1.base_query import FieldFilter
from google.api_core.exceptions import AlreadyExists

_lock = RLock()
_client = None
_version = None


def get_client():
    global _client, _version
    with _lock:
        path = Path(settings.FIRESTORE_CREDENTIALS_FILE)
        if not path.is_absolute():
            path = settings.BASE_DIR / path
        version = (path.stat().st_mtime_ns, settings.FIRESTORE_PROJECT_ID, settings.FIRESTORE_DATABASE_ID)
        if _client is None or version != _version:
            credentials = service_account.Credentials.from_service_account_file(str(path))
            project = settings.FIRESTORE_PROJECT_ID or credentials.project_id
            candidate = firestore.Client(project=project, credentials=credentials, database=settings.FIRESTORE_DATABASE_ID)
            old = _client
            _client, _version = candidate, version
            if old:
                old.close()
        return _client


class FirestoreDatabase:
    def __getattr__(self, name):
        return getattr(get_client(), name)


db = FirestoreDatabase()
