# HTTPS email for Render Free

SERVINN supports Brevo's transactional email HTTPS API. This sends verification codes and hiring notifications to Gmail or other inboxes without an SMTP connection. Google OAuth and its required email verification remain enabled.

1. Create a Brevo account at https://www.brevo.com/ and complete its account setup.
2. In Brevo's sender settings, add and verify the sender email you will use. Follow any domain authentication or transactional account activation requirements displayed by Brevo.
3. In **SMTP & API > API Keys**, generate an API key for SERVINN. Use an API key, not an SMTP key. Save it privately; never put it in GitHub or screenshots.
4. Commit and push the updated source to GitHub.
5. In **Render > servinn-system > Environment**, add:

| Key | Value |
| --- | --- |
| SERVINN_EMAIL_PROVIDER | `brevo` |
| BREVO_API_KEY | The private Brevo API key |
| DEFAULT_FROM_EMAIL | Your exact verified Brevo sender email |

6. Choose **Save, rebuild, and deploy**. After the deployment is Live, start a new Google sign-in, enter the delivered six-digit code and check Spam if necessary.
7. Check Brevo's transactional logs if an email is accepted but not delivered. Check sender verification, account activation and sending limits if requests are rejected.

Without these variables, the application retains Gmail SMTP for local development. Render's production settings intentionally ignore saved local mail credentials. SMTP credentials are not needed for Brevo HTTPS delivery. The application never automatically falls back to SMTP after an API failure.

`manage.py check_email` checks configuration presence for Brevo without sending an email. It does not prove that the API key or sender is accepted. Successful provider acceptance also does not guarantee inbox delivery.

The Free preview still uses temporary local SQLite, uploaded files and verification-code cache; restarts can invalidate sessions and codes. Brevo does not change storage persistence.

API reference: https://developers.brevo.com/docs/send-a-transactional-email
