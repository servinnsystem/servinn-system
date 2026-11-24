"""Django email backend using Brevo HTTPS, including on Render Free."""
from email.utils import parseaddr

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend
from django.core.validators import validate_email


class EmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages or []:
            if not message.recipients():
                continue
            try:
                key = getattr(settings, 'BREVO_API_KEY', '').strip()
                if not key:
                    raise ImproperlyConfigured('Configure BREVO_API_KEY in Render Environment.')
                if message.attachments:
                    raise ValueError('Attachments are not supported by this email backend.')
                name, address = parseaddr(message.from_email)
                validate_email(address)
                payload = {'sender': {'email': address, 'name': name or 'SERVINN'},
                           'subject': message.subject, 'textContent': message.body}
                for group in ('to', 'cc', 'bcc', 'reply_to'):
                    addresses = getattr(message, group)
                    if addresses:
                        recipients = []
                        for value in addresses:
                            recipient_name, recipient = parseaddr(value)
                            validate_email(recipient)
                            item = {'email': recipient}
                            if recipient_name:
                                item['name'] = recipient_name
                            recipients.append(item)
                        payload['replyTo' if group == 'reply_to' else group] = (
                            recipients[0] if group == 'reply_to' else recipients)
                response = requests.post(
                    'https://api.brevo.com/v3/smtp/email', json=payload,
                    headers={'api-key': key, 'accept': 'application/json'},
                    timeout=15, allow_redirects=False)
                # Never expose provider response bodies (they can contain private data).
                if response.status_code != 201 or not response.json().get('messageId'):
                    raise ValueError('Email provider did not accept the message.')
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise RuntimeError('HTTPS email delivery failed. Check the Brevo API key, verified sender and account limits.') from None
        return sent
