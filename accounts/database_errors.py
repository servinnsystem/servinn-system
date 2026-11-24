import logging
from google.api_core.exceptions import PermissionDenied, Unauthenticated, NotFound, ServiceUnavailable, DeadlineExceeded, ResourceExhausted
logger = logging.getLogger(__name__)


def database_error_message(error):
    if isinstance(error, (PermissionDenied, Unauthenticated)):
        return 'Firestore access is denied. The administrator must check the service-account credentials and database permissions.'
    if isinstance(error, NotFound):
        return 'The Firestore database was not found. The administrator must check the project and database configuration.'
    if isinstance(error, ResourceExhausted):
        return 'The database request limit has been reached. Please try again later.'
    return 'The account database is unavailable. The administrator must check the Cloud Firestore connection settings.'


def report_registration_error(error):
    message = database_error_message(error)
    logger.error('Registration database failure (%s). %s', type(error).__name__, message)
    return message
