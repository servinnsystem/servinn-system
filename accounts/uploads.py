from uuid import uuid4
from django.conf import settings
from django.core.files.storage import FileSystemStorage


# Keep identity documents outside the publicly served media directory.
private_storage = FileSystemStorage(location=settings.BASE_DIR / 'private_uploads')


def save_upload(upload):
    path = private_storage.save(uuid4().hex, upload)
    return {
        'path': path,
        'name': upload.name,
        'content_type': upload.content_type or 'application/octet-stream',
    }
