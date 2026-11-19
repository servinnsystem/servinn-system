"""Short-lived, single-use email challenges for verified Google sign-ins."""
import hashlib
import secrets
import time

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils.crypto import constant_time_compare, salted_hmac

LIFETIME = 600
COOLDOWN = 60
MAX_ATTEMPTS = 5


class EmailAuthError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _rate_limit(email):
    identity = hashlib.sha256(email.encode()).hexdigest()
    if not cache.add('email-auth:cooldown:' + identity, True, COOLDOWN):
        raise EmailAuthError('Please wait 60 seconds before requesting another code.', 429)
    count_key = 'email-auth:hour:' + identity
    cache.add(count_key, 0, 3600)
    if cache.incr(count_key) > 6:
        raise EmailAuthError('Too many codes requested. Please try again in an hour.', 429)


def _deliver(email, code):
    if settings.EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend' and (
            not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD):
        raise EmailAuthError('Email delivery is not configured. The SERVINN administrator must configure the Gmail sender account.', 503)
    try:
        sent = send_mail(
            'Your SERVINN verification code',
            f'Your SERVINN verification code is: {code}\n\n'
            'Enter this code in the SERVINN page where you started Google sign-in. '
            'It expires in 10 minutes and can be used once.\n\n'
            'Do not share this code. If you did not request it, ignore this email.',
            settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
        if sent != 1:
            raise ValueError('Message not accepted')
    except Exception:
        raise EmailAuthError('Unable to send your code. Please try again or contact the SERVINN administrator.', 503)


def issue(pending):
    _rate_limit(pending['email'])
    token = secrets.token_urlsafe(32)
    code = f'{secrets.randbelow(1000000):06d}'
    _deliver(pending['email'], code)
    challenge = dict(pending, code_hash=salted_hmac('servinn-email-code', token + ':' + code).hexdigest(),
                     expires_at=time.time() + LIFETIME)
    cache.set('email-auth:challenge:' + token, challenge, LIFETIME)
    cache.set('email-auth:attempts:' + token, 0, LIFETIME)
    return token


def pending_for(token):
    challenge = cache.get('email-auth:challenge:' + token) if isinstance(token, str) else None
    if not challenge or challenge['expires_at'] <= time.time():
        raise EmailAuthError('Your code expired. Please start Google sign-in again.')
    return challenge


def resend(token):
    pending = pending_for(token)
    _rate_limit(pending['email'])
    code = f'{secrets.randbelow(1000000):06d}'
    _deliver(pending['email'], code)
    pending['code_hash'] = salted_hmac('servinn-email-code', token + ':' + code).hexdigest()
    cache.set('email-auth:challenge:' + token, pending,
              max(1, int(pending['expires_at'] - time.time())))


def consume(token, code):
    pending = pending_for(token)
    try:
        attempts = cache.incr('email-auth:attempts:' + token)
    except ValueError:
        raise EmailAuthError('Your code expired. Please start Google sign-in again.')
    if attempts > MAX_ATTEMPTS:
        cache.delete('email-auth:challenge:' + token)
        raise EmailAuthError('Too many incorrect attempts. Please start Google sign-in again.', 429)
    expected = salted_hmac('servinn-email-code', token + ':' + str(code)).hexdigest()
    if not (isinstance(code, str) and len(code) == 6 and code.isascii() and code.isdigit()
            and constant_time_compare(expected, pending['code_hash'])):
        if attempts >= MAX_ATTEMPTS:
            cache.delete('email-auth:challenge:' + token)
            raise EmailAuthError('Too many incorrect attempts. Please start Google sign-in again.', 429)
        raise EmailAuthError('Incorrect code. Check your email and try again.')
    if not cache.add('email-auth:used:' + token, True, LIFETIME):
        raise EmailAuthError('This code has already been used. Please start Google sign-in again.')
    cache.delete('email-auth:challenge:' + token)
    cache.delete('email-auth:attempts:' + token)
    return pending
