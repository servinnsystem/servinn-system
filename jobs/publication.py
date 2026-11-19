"""Publication rules shared by every job listing and action."""
from datetime import datetime
from django.utils import timezone


def is_published(job):
    return job.get('status') == 'Active' and job.get('review_status') == 'Approved'


def pending_review():
    return {'status': 'Pending Review', 'review_status': 'Pending',
            'submitted_at': timezone.now(), 'review_note': '',
            'reviewed_by': None, 'reviewed_at': None, 'published_at': None}


def update_snapshot(db, reference, snapshot, changes):
    # Refuse to approve or overwrite content changed since it was read.
    version = getattr(snapshot, 'update_time', None)
    if isinstance(version, datetime):
        reference.update(changes, option=db.write_option(last_update_time=version))
    else:
        reference.update(changes)
