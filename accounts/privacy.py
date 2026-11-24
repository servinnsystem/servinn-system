"""Public notice for applicants, available before any account data is submitted."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import render
from django.views.decorators.http import require_GET

POLICY_VERSION = '2026-11-20.1'

@require_GET
def privacy_policy(request):
    contact_email = settings.PRIVACY_CONTACT_EMAIL.strip()
    try:
        validate_email(contact_email)
    except ValidationError:
        contact_email = ''
    return render(request, 'accounts/privacy_policy.html', {
        'policy_version': POLICY_VERSION, 'contact_email': contact_email,
        'controller_name': settings.PRIVACY_CONTROLLER_NAME,
    })
