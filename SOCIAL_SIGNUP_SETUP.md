# Direct Google OAuth sign-in

SERVINN uses Google's standard OAuth 2.0 authorization-code flow with OpenID Connect. Firebase Authentication and its browser/Admin SDKs are no longer used. Email/password login, Django administrator authentication, Firestore records and the extra email verification code remain in place.

## 1. Create Google OAuth credentials

1. Open https://console.cloud.google.com/ and select your Google Cloud project. An existing project can be reused.
2. Open **Google Auth Platform**. Configure Branding, Audience and Data Access (consent screen). Request only `openid`, `email` and `profile`.
3. If the app is in testing mode, add the Google accounts you will use under test users.
4. Open **Clients** (or APIs & Services > Credentials), create an OAuth client ID, and choose **Web application**.
5. Add this exact authorized redirect URI for local development:

   `http://127.0.0.1:8000/accounts/google-callback/`

   If SERVINN is opened through localhost instead, add `http://localhost:8000/accounts/google-callback/` and configure that exact address in SERVINN. The host must match the browser's sign-in host so the session cookie is returned. For deployment, use the site's HTTPS address with the same callback path.
6. Copy the client ID and client secret privately. This is an OAuth client credential, not a service-account JSON key, Firebase API key, or Gmail App Password.

Google's setup and flow documentation:
https://developers.google.com/identity/protocols/oauth2/web-server
https://developers.google.com/identity/openid-connect/openid-connect

## 2. Save credentials in SERVINN

1. Sign in to the administrator portal using your existing administrator credentials.
2. Open **Sign-in settings** (`/portal-admin/sign-in-settings/`).
3. Under **Google OAuth credentials**, enter the client ID, client secret, and exact authorized redirect URI.
4. Choose **Save Google OAuth credentials**. The secret is encrypted in `.runtime/google-oauth.enc` and is never redisplayed. Keep the Django secret key stable across server restarts.
5. Under Gmail sender, keep or configure the sender used for the additional six-digit email code. OAuth credentials and Gmail sender credentials are separate.

No terminal feature-management command is needed. Alternatively, set `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` and `GOOGLE_OAUTH_REDIRECT_URI` in the private `.env` file and restart the server. The alternative names `AUTH_GOOGLE_ID` and `AUTH_GOOGLE_SECRET` are also accepted. Saved admin configuration takes precedence over environment values.

## 3. Sign in

Choose **Continue with Google** or **Sign up with Google**. The browser goes directly to Google's account selection page, then returns to SERVINN's callback. Enter the six-digit email code. New users continue to profile setup; existing users retain their profile, password and role.

Existing accounts migrated from Firebase link to the verified Google `sub` only after the email code is confirmed. A legacy `firebase_uid` is not compared with a Google subject: they are different identifiers. Historical fields may remain in stored account payloads for reference, but are not used to authenticate.

## Security and error behavior

- Each authorization request has a random, short-lived state, nonce and PKCE verifier/challenge.
- The callback consumes its session state once. Server-to-server code exchange uses the client secret and verifier with bounded network timeouts.
- Google's Python authentication library verifies the ID token. SERVINN also checks issuer, audience, authorized party, nonce, verified email and subject.
- Access tokens, authorization codes, ID tokens and client secrets are never placed in application account records or browser code. No refresh token is requested.
- Only the verified Google identity supplies the account email. An existing Google subject binding is rechecked after email-code verification.
- Failed or cancelled sign-in returns to the login page with a recoverable error popup. Existing Firebase-based verification challenges cannot finish a new OAuth login.
- The already-hidden Firebase phone-login endpoint is retired and returns HTTP 410. Email/password, Google OAuth and administrator login remain supported.

## Troubleshooting

- **redirect_uri_mismatch:** match the saved callback URI exactly in both Google Cloud and SERVINN, including the trailing slash, host, scheme and port.
- **access_denied / test user error:** add the Google account as a test user or finish the consent-screen publishing requirements.
- **invalid_client:** check that the Web application client ID and secret belong to the same client.
- **expired or unverifiable sign-in:** restart sign-in in one browser tab; state expires after ten minutes.
- **Email not configured:** save the Gmail sender separately in Sign-in settings.

For an optional configuration check without displaying credentials:

```powershell
.\env\Scripts\python.exe manage.py check_google_oauth
```

This validates configuration shape only. A real browser sign-in is needed to confirm that Google accepts the configured client credentials and redirect URI.

## Application database: Cloud Firestore

Application profiles, jobs, applications, saved jobs and ratings now use Cloud Firestore. Configure FIRESTORE_PROJECT_ID, FIRESTORE_DATABASE_ID and FIRESTORE_CREDENTIALS_FILE in the private .env file. The service-account JSON is a database credential and is separate from the Google OAuth client ID and secret.

Django administrator accounts and browser sessions use the local db.sqlite3 file. Keep that file, private_uploads/, media/ and .runtime/ backed up. No PostgreSQL driver, Prisma project connection or DATABASE_URL is required by SERVINN.

The completed PostgreSQL-to-Firestore transfer was verified for all 14 source application records. Recovery copies of the previous database data and administrator accounts are saved privately under the directory listed in .runtime/firestore-cutover.json.

To check the database connection without changing data:

```powershell
.\env\Scripts\python.exe manage.py check_database
```

For database access protection, publish `firestore.rules` using the instructions in [Firestore security](docs/FIRESTORE_SECURITY.md). The rules block direct client access; Django server access remains governed by IAM and application authorization.
