"""Direct Google OAuth 2.0 / OpenID Connect; no Firebase dependency."""
import base64
import hashlib
import json
import os
import secrets
import tempfile
import time
from urllib.parse import urlencode, urlsplit
import requests
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from .mail_settings import _cipher


class OAuthError(Exception):
    pass


def load_config():
    path = settings.BASE_DIR / '.runtime/google-oauth.enc'
    if path.exists() and not getattr(settings, 'SERVINN_OAUTH_IGNORE_SAVED', False):
        try:
            return json.loads(_cipher().decrypt(path.read_bytes()))
        except Exception:
            raise OAuthError('Saved Google OAuth credentials could not be read. The administrator must re-enter them in Sign-in settings.') from None
    return {'client_id': settings.GOOGLE_OAUTH_CLIENT_ID, 'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
            'redirect_uri': settings.GOOGLE_OAUTH_REDIRECT_URI}


def validate_config(config):
    if not config.get('client_id', '').endswith('.apps.googleusercontent.com') or not config.get('client_secret'):
        raise OAuthError('Google OAuth is not configured. Ask the administrator to open Sign-in settings and save Google OAuth credentials.')
    uri = urlsplit(config.get('redirect_uri', ''))
    if (uri.username or uri.password or uri.query or uri.fragment or not uri.hostname
            or uri.path != '/accounts/google-callback/'
            or (uri.scheme != 'https' and not (uri.scheme == 'http' and uri.hostname in ('localhost', '127.0.0.1', '::1')))):
        raise OAuthError('Use an HTTPS Google callback URL ending in /accounts/google-callback/. HTTP is allowed only for localhost.')
    return config


def save_config(config):
    validate_config(config)
    path = settings.BASE_DIR / '.runtime/google-oauth.enc'
    path.parent.mkdir(mode=0o700, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            output.write(_cipher().encrypt(json.dumps(config).encode()))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def authorization(request):
    config = validate_config(load_config())
    role = request.GET.get('role', 'job_seeker')
    if role not in ('job_seeker', 'employer'):
        raise OAuthError('Choose a job seeker or employer account.')
    callback = urlsplit(config['redirect_uri'])
    if request.get_host().casefold() != callback.netloc.casefold():
        # Keep the OAuth state cookie on the same host Google will return to.
        return f'{callback.scheme}://{callback.netloc}/accounts/google-login/?' + urlencode({'role': role})
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    request.session.cycle_key()
    request.session['google_oauth'] = {'state': state, 'nonce': nonce, 'verifier': verifier, 'role': role,
                                     'started': time.time(), 'client_id': config['client_id'], 'redirect_uri': config['redirect_uri']}
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
        'client_id': config['client_id'], 'redirect_uri': config['redirect_uri'], 'response_type': 'code',
        'scope': 'openid email profile', 'state': state, 'nonce': nonce, 'prompt': 'select_account',
        'code_challenge': challenge, 'code_challenge_method': 'S256'})


class TimedRequest(Request):
    def __call__(self, *args, **kwargs):
        kwargs['timeout'] = 15
        return super().__call__(*args, **kwargs)


def exchange(request):
    flow = request.session.pop('google_oauth', None)
    state = request.GET.get('state', '')
    if (not flow or not isinstance(state, str) or not state.isascii() or not secrets.compare_digest(state, flow['state'])
            or not 0 <= time.time() - flow['started'] <= 600):
        raise OAuthError('Google sign-in expired or could not be verified. Please start again.')
    if request.GET.get('error'):
        raise OAuthError('Google sign-in was cancelled or denied. You can try again.')
    code = request.GET.get('code', '')
    if not code or len(code) > 8192:
        raise OAuthError('Google did not return an authorization code. Please start again.')
    config = validate_config(load_config())
    if config['client_id'] != flow['client_id'] or config['redirect_uri'] != flow['redirect_uri']:
        raise OAuthError('Google sign-in settings changed. Please start again.')
    try:
        response = requests.post('https://oauth2.googleapis.com/token', data={
            'client_id': config['client_id'], 'client_secret': config['client_secret'],
            'redirect_uri': flow['redirect_uri'], 'code': code, 'grant_type': 'authorization_code',
            'code_verifier': flow['verifier']}, timeout=15, allow_redirects=False)
        response.raise_for_status()
        token = response.json()['id_token']
        if not isinstance(token, str) or len(token) > 32768:
            raise ValueError()
        with requests.Session() as session:
            claims = id_token.verify_oauth2_token(token, TimedRequest(session=session), audience=config['client_id'])
        if (claims.get('iss') not in ('accounts.google.com', 'https://accounts.google.com')
                or claims.get('aud') != config['client_id']
                or claims.get('azp', config['client_id']) != config['client_id']
                or not secrets.compare_digest(str(claims.get('nonce', '')), flow['nonce'])
                or claims.get('email_verified') is not True
                or not isinstance(claims.get('sub'), str) or not claims['sub']):
            raise ValueError()
        validate_email(claims.get('email', ''))
    except Exception:
        raise OAuthError('Unable to verify Google sign-in. Please try again; contact the administrator if the problem continues.') from None
    return claims, flow['role']
