from django import forms
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from accounts.decorators import role_required
from accounts.mail_settings import load_mail, save_mail, test_mail


class SignInSettingsForm(forms.Form):
    sender = forms.EmailField(label='Gmail sender address')
    app_password = forms.CharField(required=False, label='Gmail App Password', widget=forms.PasswordInput,
                                   help_text='Leave blank to keep the saved password. Your normal Gmail password will not work.')

    def clean_sender(self):
        sender = self.cleaned_data['sender'].strip().lower()
        if not sender.endswith('@gmail.com'):
            raise forms.ValidationError('Enter the Gmail address that owns the App Password.')
        return sender

    def clean_app_password(self):
        password = ''.join(self.cleaned_data['app_password'].split())
        if password and (len(password) != 16 or not password.isascii() or not password.isalpha()):
            raise forms.ValidationError('Enter the 16-letter Gmail App Password.')
        return password


class GoogleOAuthForm(forms.Form):
    client_id = forms.RegexField(r'^[A-Za-z0-9._-]+\.apps\.googleusercontent\.com$', max_length=300, label='Google OAuth client ID')
    client_secret = forms.CharField(required=False, max_length=512, label='Google OAuth client secret',
                                   widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
                                   help_text='Leave blank to keep the saved secret for the same client ID.')
    redirect_uri = forms.URLField(max_length=500, label='Authorized redirect URI',
                                  help_text='Must exactly match the callback URL registered in Google Cloud.')


@never_cache
@sensitive_post_parameters('app_password', 'client_secret')
@role_required(['admin'])
def signin_settings(request):
    try:
        config = load_mail()
    except Exception:
        config = {}
        messages.error(request, 'Saved email settings could not be read. Re-enter the sender and App Password.')
    form = SignInSettingsForm(request.POST if request.method == 'POST' and request.POST.get('action') == 'mail' else None,
                              initial={'sender': config.get('sender', '')})
    from accounts.google_oauth import load_config
    try:
        oauth_config = load_config()
    except Exception:
        oauth_config = {}
        messages.error(request, 'Google OAuth settings could not be read. Re-enter the credentials.')
    oauth_form = GoogleOAuthForm(request.POST if request.method == 'POST' and request.POST.get('action') == 'google' else None,
                                 initial={'client_id': oauth_config.get('client_id', ''), 'redirect_uri': oauth_config.get('redirect_uri', '')})
    diagnostics = None
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'mail' and form.is_valid():
            sender = form.cleaned_data['sender']
            password = form.cleaned_data['app_password'] or (config.get('password', '') if sender == config.get('sender') else '')
            if not password:
                form.add_error('app_password', 'Enter an App Password for this sender.')
            else:
                try:
                    if not test_mail(sender, password):
                        raise ValueError()
                    save_mail(sender, password)
                except Exception:
                    form.add_error(None, 'Gmail connection failed. Check the sender, App Password, and server internet connection. Settings were not changed.')
                else:
                    messages.success(request, 'Gmail connection verified and settings saved. Verification and acceptance emails now use this sender.')
                    return redirect('admin_signin_settings')
        elif action == 'google' and oauth_form.is_valid():
            proposed = dict(oauth_form.cleaned_data)
            if not proposed['client_secret'] and proposed['client_id'] == oauth_config.get('client_id'):
                proposed['client_secret'] = oauth_config.get('client_secret', '')
            try:
                from accounts.google_oauth import save_config, OAuthError
                save_config(proposed)
            except OAuthError as error:
                oauth_form.add_error(None, str(error))
            except Exception:
                oauth_form.add_error(None, 'Unable to save Google OAuth settings. Please try again.')
            else:
                messages.success(request, 'Google OAuth credentials saved. Ensure the callback URL is registered in Google Cloud, then test sign-in.')
                return redirect('admin_signin_settings')
        elif action == 'check':
            from servinn_core.firestore_config import db
            try:
                next(iter(db.collection('users').limit(1).stream(timeout=10, retry=None)), None)
                diagnostics = 'Cloud Firestore connection is ready.'
            except Exception:
                diagnostics = 'Firestore connection failed. Check the project, database and service-account credentials.'
    return render(request, 'admin_panel/signin_settings.html', {'form': form, 'mail_configured': bool(config.get('password')), 'diagnostics': diagnostics, 'oauth_form': oauth_form, 'oauth_configured': bool(oauth_config.get('client_id') and oauth_config.get('client_secret'))})
