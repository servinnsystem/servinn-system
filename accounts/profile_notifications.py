"""Notify applicants after the administrator saves a profile review decision."""
from django.core.mail import send_mail
from django.core.validators import validate_email
from .mail_settings import delivery_options, sender_address


def send_profile_decision(email, profile, notes, status):
    if status not in ('Verified', 'Rejected'):
        raise ValueError('Unsupported profile notification decision.')
    validate_email(email)
    options = delivery_options()
    name = profile.get('first_name') or 'Applicant'
    if status == 'Verified':
        result = 'Your SERVINN job seeker profile has been verified and approved by an administrator.'
        next_steps = 'Sign in to SERVINN to find matching job opportunities and apply for jobs.'
    else:
        result = 'Your SERVINN job seeker profile was reviewed by an administrator and was not approved.'
        next_steps = ('Sign in to SERVINN and open Documents & corrections to review the feedback '
                      'and submit corrected information or documents for another review.')
    body = f'Hello {name},\n\n{result}\n\n'
    if notes.strip():
        body += f'Reason or feedback from the administrator:\n{notes.strip()}\n\n'
    body += (next_steps + '\n\nContact the SERVINN administrator if you have questions.\n\n'
             'Do not reply with passwords, verification codes or identity documents.\n\nSERVINN')
    if send_mail(f'SERVINN: Your profile is {status.lower()}', body, sender_address(),
                 [email], fail_silently=False, **options) != 1:
        raise RuntimeError('Email provider did not accept the notification.')
