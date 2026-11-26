"""Email applicants only after a hiring decision has been saved."""
import hashlib
import json
from zoneinfo import ZoneInfo
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.utils import timezone


class ApplicationEmailError(Exception):
    pass


def notification_fingerprint(application):
    details = {key: application.get(key) or '' for key in
               ('status', 'candidate_message', 'interview_at', 'interview_location')}
    return hashlib.sha256(json.dumps(details, sort_keys=True, default=str).encode()).hexdigest()


def send_application_email(reference, application):
    status = application.get('status')
    if status not in ('Accepted', 'Hired', 'Rejected', 'Interview Invitation'):
        return False
    fingerprint = notification_fingerprint(application)
    if application.get('application_email_fingerprint') == fingerprint:
        return False
    recipient = application.get('applicant_email', '')
    try:
        validate_email(recipient)
    except ValidationError:
        raise ApplicationEmailError('The applicant has no valid email address.')
    from accounts.mail_settings import delivery_options, sender_address
    try:
        options = delivery_options()
    except Exception:
        raise ApplicationEmailError('The administrator must configure the email provider and sender account.') from None
    title = application.get('job_title') or 'the position you applied for'
    company = application.get('company_name') or 'the employer'
    name = application.get('applicant_name') or 'Applicant'
    if status == 'Interview Invitation':
        subject = 'SERVINN: You are invited to an interview'
        decision = f'{company} has invited you to an interview for {title} on SERVINN.'
    elif status == 'Rejected':
        subject = 'SERVINN: Update on your job application'
        decision = f'{company} did not select your application for {title} on SERVINN. You can continue exploring other opportunities.'
    elif status == 'Hired':
        subject = 'SERVINN: You have been marked hired'
        decision = f'Congratulations! {company} has marked you hired for {title} on SERVINN.'
    else:
        subject = 'SERVINN: Your job application has been accepted'
        decision = f'Congratulations! {company} has accepted your application for {title} on SERVINN.'
    body = f'Hello {name},\n\n{decision}\n\n'
    if status == 'Interview Invitation':
        schedule = application.get('interview_at')
        if schedule and hasattr(schedule, 'tzinfo'):
            if timezone.is_naive(schedule):
                schedule = timezone.make_aware(schedule, ZoneInfo('Asia/Manila'))
            schedule = timezone.localtime(schedule, ZoneInfo('Asia/Manila')).strftime('%B %d, %Y at %I:%M %p')
            body += f'Interview schedule: {schedule} (Asia/Manila)\n'
        location = application.get('interview_location') or 'Check My applications for the location.'
        body += f'Interview address or meeting link: {location}\n\n'
    body += 'Sign in to SERVINN and open My applications to review the decision and next steps.\n'
    note = application.get('candidate_message', '').strip()
    if note:
        body += f'\nMessage from your employer:\n{note}\n'
    body += '\nThank you for using SERVINN.'
    try:
        sent = send_mail(subject, body,
                         sender_address(), [recipient], fail_silently=False, **options)
        if sent != 1:
            raise ValueError('Email not accepted by the mail server')
    except Exception:
        raise ApplicationEmailError('Email delivery failed. Check the sender configuration and try again.')
    try:
        updates = {'application_email_sent_at': timezone.now(),
                   'application_email_fingerprint': fingerprint, 'application_email_status': status}
        if status == 'Accepted':
            updates['acceptance_email_sent_at'] = updates['application_email_sent_at']
        reference.update(updates)
    except Exception:
        raise ApplicationEmailError('The email was sent, but its delivery record could not be saved.')
    return True
