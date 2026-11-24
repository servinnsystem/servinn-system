# Temporary free preview on Render

This configuration is a preview, not durable hosting. Firestore stays remote, but the local SQLite administrator accounts, sessions and uploaded files can disappear after a restart or deployment. Existing Firestore file metadata does not transfer files from your PC. Use test accounts and sample files only; do not upload real identity documents.

Render Free blocks Gmail SMTP ports. Configure the supported Brevo HTTPS backend using [Brevo email setup](BREVO_EMAIL_SETUP.md) to send verification codes and hiring emails. Do not bypass email verification to work around email configuration.

## Push the prepared files

In VS Code, commit the deployment files and Sync Changes to GitHub. Keep `.env`, `.runtime`, `env`, SQLite and upload folders excluded. Never commit the Firestore key.

## Render service fields

- Source: `servinnsystem/servinn-system`, branch `main`
- Language: Python 3; region: Singapore; root directory: blank
- Compute: Free
- Build command: `bash build.sh`
- Start command: `bash start.sh`

## Environment variables

Set these before deploying. Do not include quotes around values in Render's value fields.

| Key | Value |
| --- | --- |
| DJANGO_SETTINGS_MODULE | `servinn_core.render_settings` |
| DJANGO_SECRET_KEY | Click Generate; use a stable random value of at least 50 characters |
| FIRESTORE_PROJECT_ID | Your actual Firebase project ID from the local private configuration |
| FIRESTORE_DATABASE_ID | `(default)` |
| FIRESTORE_CREDENTIALS_FILE | `/etc/secrets/firestore-service-account.json` |
| GOOGLE_OAUTH_CLIENT_ID | Your Google OAuth client ID |
| GOOGLE_OAUTH_CLIENT_SECRET | Your Google OAuth client secret |
| GOOGLE_OAUTH_REDIRECT_URI | `https://YOUR-ACTUAL-RENDER-HOST/accounts/google-callback/` |

Render supplies `RENDER_EXTERNAL_HOSTNAME`; the app automatically allows this hostname. Custom domains also need `DJANGO_ALLOWED_HOSTS` as a comma-separated list of hostnames without `https://` or paths.

In **Advanced / Secret Files**, add a file named `firestore-service-account.json` containing the private JSON from `.runtime/firestore-service-account.json`. Render mounts it at `/etc/secrets/firestore-service-account.json`. Do not paste this key in chat or GitHub.

Add the exact HTTPS callback URL to the Google OAuth client's authorized redirect URIs. The actual Render hostname may differ from the requested service name. Updating OAuth settings does not remove the Free plan's email restriction.

## After deployment

Open the public site, check CSS and images, view Privacy Policy and test job search. The preview connects to your configured Firestore database, so submitted profile/job changes affect that database. Local administrator accounts are not copied from your PC. A paid hosting plan with persistent storage or external durable replacements is needed before reliable use of administrator accounts and identity uploads. Configure the Brevo HTTPS email backend described above for email on Free.

References:
- https://render.com/docs/deploy-django
- https://render.com/docs/free
- https://render.com/docs/configure-environment-variables
