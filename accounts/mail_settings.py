"""Persist mail credentials encrypted at rest, outside publicly served folders."""
import base64
import hashlib
import json
import os
import tempfile
from pathlib import Path
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.mail import get_connection


def _path():
    return Path(settings.BASE_DIR) / '.runtime' / 'mail.enc'


def _cipher():
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()))


def load_mail():
    path = _path()
    if path.exists() and not getattr(settings, 'SERVINN_MAIL_IGNORE_SAVED', False):
        return json.loads(_cipher().decrypt(path.read_bytes()))
    return {'sender': settings.EMAIL_HOST_USER, 'password': settings.EMAIL_HOST_PASSWORD}


def save_mail(sender, password):
    path = _path()
    path.parent.mkdir(mode=0o700, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            output.write(_cipher().encrypt(json.dumps({'sender': sender, 'password': password}).encode()))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def delivery_options():
    if settings.EMAIL_BACKEND == 'accounts.brevo_backend.EmailBackend':
        if not getattr(settings, 'BREVO_API_KEY', '') or not settings.DEFAULT_FROM_EMAIL or settings.DEFAULT_FROM_EMAIL.endswith('@servinn.local'):
            raise ValueError('Configure BREVO_API_KEY and DEFAULT_FROM_EMAIL with a verified Brevo sender in Render Environment.')
        return {}
    if settings.EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend':
        return {}
    config = load_mail()
    if not config.get('sender') or not config.get('password'):
        raise ValueError('Email delivery is not configured. Open Administration > Sign-in settings to configure the Gmail sender account.')
    return {'auth_user': config['sender'], 'auth_password': config['password']}


def sender_address():
    if settings.EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend':
        return load_mail().get('sender') or settings.DEFAULT_FROM_EMAIL
    return settings.DEFAULT_FROM_EMAIL


def test_mail(sender, password):
    with get_connection(backend='django.core.mail.backends.smtp.EmailBackend',
                        host='smtp.gmail.com', port=587, username=sender,
                        password=password, use_tls=True, timeout=10) as connection:
        return connection.connection is not None
