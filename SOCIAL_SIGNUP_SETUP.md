# SERVINN Google signup

The Google signup button authenticates with Firebase, then sends a verified ID
token to Django. SERVINN emails a six-digit code to the selected Google address.
After the code is confirmed, new accounts continue to Profile setup; existing
completed accounts go to their dashboard. No Google password is stored by SERVINN.

## Configuration

Google sign-in is enabled for `servinnsystem-bf596`. Both `localhost` and
`127.0.0.1` are authorized domains (verified November 15, 2026).

## Test signup

1. Run `python manage.py runserver`.
2. Open `http://127.0.0.1:8000/accounts/register/`.
3. Click **Sign up with Google** and select an account.
4. Open your Gmail inbox and enter the six-digit SERVINN code on the verification page.
5. After verification, a new user should reach `/accounts/create-profile/`.
6. Complete profile setup and accept the user agreement.

## Configure the Gmail sender (required for delivery)

### Guided startup

Stop any running SERVINN server, then run this in the project PowerShell terminal:

```powershell
.\run_with_gmail.ps1
```

Enter the sender Gmail address and its **App Password** when prompted. Password
input is hidden. The helper checks the SMTP login without sending mail, then
starts SERVINN in the same process environment. Keep that terminal open while
using the app. Credentials are not saved to source files and are cleared from
the script's environment when the server stops.

If PowerShell blocks the script under its execution policy, use the manual
environment-variable commands below. No execution-policy change is required.

To check an already configured terminal without starting the server, run
`python manage.py check_email`.

### Manual setup

The recipient is the Google account selected during signup. The sender is a Gmail
account owned by the SERVINN operator. Configure the sender once on the server.

1. Enable **2-Step Verification** for the Gmail sender account.
2. Create an [App Password](https://myaccount.google.com/apppasswords) for SERVINN.
   Some organization or protected accounts do not offer App Passwords; use a
   supported SMTP sender if your account cannot create one.
3. Stop the development server. In the PowerShell terminal where you start SERVINN,
   run the following. Replace the email address with your sender address; enter
   the App Password when prompted, without spaces. Do not use your normal Gmail password.

   ```powershell
   $env:EMAIL_HOST_USER = "your-sender@gmail.com"
   $servinnMailSecret = Read-Host "Gmail App Password" -AsSecureString
   $env:EMAIL_HOST_PASSWORD = [System.Net.NetworkCredential]::new("", $servinnMailSecret).Password
   python manage.py runserver
   ```

   The password is not echoed or written into your source files. These environment
   settings apply to this terminal and the server it starts; configure equivalent
   environment variables in your hosting service for deployment.

SMTP defaults to `smtp.gmail.com`, port `587`, using TLS. Optional environment
variables are `EMAIL_HOST`, `EMAIL_PORT`, and `DEFAULT_FROM_EMAIL`.

Until the sender is configured, signup reports an email-configuration error and
does not create an account or an authenticated session. Emails are sent only when
a user initiates Google sign-in or requests another code.

## Verification behavior

- Codes expire after 10 minutes and can be used only once.
- Resends require a 60-second wait; up to six sends are allowed per address per hour.
- Five incorrect attempts invalidate the challenge.
- A resend invalidates the previous code without extending the original expiry.
- Codes are never included in browser responses, session data, or application logs.
- Email confirmation is separate from administrator profile/document approval.
- Verification state uses Django's cache. The default local cache works with the
  single-process development server; restarting clears pending challenges.
  Configure a shared cache supporting atomic `add` and `incr` for multi-process
  hosting so all workers use the same challenges and rate limits.

If the browser blocks the sign-in window, allow popups for SERVINN and try again.

Login and signup pages use `Cross-Origin-Opener-Policy: same-origin-allow-popups`
so the Google popup can communicate with the page. Other pages keep Django's
default opener policy.

If the popup still fails, a **Continue with Google in this tab** button is offered.
This optional redirect flow remembers the account type and finishes signup when
Google returns. Browsers that block cross-site storage can also block Firebase
redirect results. For hosted deployments, follow
[Firebase's redirect configuration guidance](https://firebase.google.com/docs/auth/web/redirect-best-practices).
The popup flow remains available if a redirect returns no result.

[Official Firebase Google sign-in instructions](https://firebase.google.com/docs/auth/web/google-signin)

[Google App Password instructions](https://support.google.com/accounts/answer/185833)
