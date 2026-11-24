# Firestore security for SERVINN

SERVINN uses the Python server SDK with a private service account. Browsers send requests to Django, which checks the signed-in user's role and ownership. Google OAuth sign-in does not create a Firebase Authentication session.

The root `firestore.rules` file blocks all direct web/mobile reads and writes, including nested ratings. Public job searches still go through Django. Do not add a public read rule for user profiles, applications or identity document metadata.

## Publish the rules

1. Open Firebase Console and select the project used by `FIRESTORE_PROJECT_ID` in your private `.env`.
2. Open **Firestore Database**, select the database matching `FIRESTORE_DATABASE_ID`, then open **Rules**.
3. Replace the existing rules with the contents of the project's `firestore.rules` file.
4. Click **Publish**. Saving the local file alone does not change cloud rules.
5. Use the Rules playground to test a read and a write against `users/example` and `job_postings/example/ratings/example`. Both anonymous and authenticated client requests should be denied.
6. Check SERVINN's dashboards and run `env\Scripts\python.exe manage.py check_database`. Server access should still work.

## Server access is controlled separately

Firestore server SDKs bypass Security Rules and use Google Cloud IAM. These rules do not restrict a stolen service-account key or replace Django authorization. Give the runtime service account only the database permissions it needs (normally `roles/datastore.user`), rather than project Owner or Editor. Review existing IAM bindings before changing them.

Keep `.runtime/firestore-service-account.json`, `.env`, encrypted sign-in settings and private backups outside publicly served directories and Git. Identity files stay in private upload storage and must be served through Django's authorized file endpoint.

Firebase reference: https://firebase.google.com/docs/firestore/security/insecure-rules
