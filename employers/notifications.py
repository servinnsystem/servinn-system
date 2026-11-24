"""Email applicants only after a hiring decision has been saved."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.utils import timezone


class AcceptanceEmailError(Exception):
    pass


def send_acceptance_email(reference, application):
    if application.get('status') not in ('Accepted', 'Hired') or application.get('acceptance_email_sent_at'):
        return False
    recipient = application.get('applicant_email', '')
    try:
        validate_email(recipient)
    except ValidationError:
        raise AcceptanceEmailError('The applicant has no valid email address.')
    from accounts.mail_settings import delivery_options, sender_address
    try:
        options = delivery_options()
    except Exception:
        raise AcceptanceEmailError('The administrator must configure the email provider and sender account.') from None
    title = application.get('job_title') or 'the position you applied for'
    company = application.get('company_name') or 'the employer'
    name = application.get('applicant_name') or 'Applicant'
    body = (f'Hello {name},\n\nCongratulations! {company} has accepted your application '
            f'for {title} on SERVINN.\n\n'
            'Sign in to SERVINN and open My applications to review the decision and next steps.\n')
    note = application.get('candidate_message', '').strip()
    if note:
        body += f'\nMessage from your employer:\n{note}\n'
    body += '\nThank you for using SERVINN.'
    try:
        sent = send_mail('SERVINN: Your job application has been accepted', body,
                         sender_address(), [recipient], fail_silently=False, **options)
        if sent != 1:
            raise ValueError('Email not accepted by the mail server')
    except Exception:
        raise AcceptanceEmailError('Email delivery failed. Check the sender configuration and try again.')
    try:
        reference.update({'acceptance_email_sent_at': timezone.now()})
    except Exception:
        raise AcceptanceEmailError('The email was sent, but its delivery record could not be saved.')
    return True
