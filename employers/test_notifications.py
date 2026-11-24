from unittest.mock import Mock, patch
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from django.test import SimpleTestCase, RequestFactory, override_settings
from django.utils import timezone
from employers.views import update_applicant_status


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', DEFAULT_FROM_EMAIL='servinn@example.com')
class AcceptanceNotificationTests(SimpleTestCase):
    def request(self, status='Accepted'):
        request = RequestFactory().post('/', {'status': status, 'candidate_message': 'Please contact us for your start date.'})
        request.session = {'user_role': 'employer', 'user_email': 'owner@example.com'}
        request._messages = FallbackStorage(request)
        return request

    def application(self, db, **changes):
        ref = db.collection.return_value.document.return_value
        ref.get.return_value.to_dict.return_value = {
            'employer_email': 'owner@example.com', 'applicant_email': 'applicant@gmail.com',
            'applicant_name': 'Ana', 'job_title': 'Nanny', 'company_name': 'Example Company',
            'status': 'Reviewed', **changes}
        return ref

    @patch('employers.views.db')
    def test_acceptance_saves_decision_then_emails_applicant(self, db):
        ref = self.application(db)
        def verify_saved(*args, **kwargs):
            self.assertEqual(ref.update.call_args.args[0]['status'], 'Accepted')
            return 1
        with patch('employers.notifications.send_mail', side_effect=verify_saved) as send:
            update_applicant_status(self.request(), 'application')
        self.assertEqual(send.call_args.args[3], ['applicant@gmail.com'])
        self.assertIn('Nanny', send.call_args.args[1])
        self.assertIn('Example Company', send.call_args.args[1])
        self.assertIn('Please contact us', send.call_args.args[1])
        self.assertIn('acceptance_email_sent_at', ref.update.call_args.args[0])

    @patch('employers.views.db')
    def test_real_django_email_backend_receives_message(self, db):
        self.application(db)
        update_applicant_status(self.request(), 'application')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['applicant@gmail.com'])

    @patch('employers.notifications.send_mail')
    @patch('employers.views.db')
    def test_no_email_for_other_decisions_or_wrong_owner(self, db, send):
        for status in ('Reviewed', 'Shortlisted', 'Rejected'):
            self.application(db)
            update_applicant_status(self.request(status), 'application')
        self.application(db, employer_email='other@example.com')
        update_applicant_status(self.request(), 'application')
        send.assert_not_called()

    @patch('employers.notifications.send_mail')
    @patch('employers.views.db')
    def test_already_sent_acceptance_is_not_resent_on_hiring(self, db, send):
        self.application(db, status='Accepted', acceptance_email_sent_at=timezone.now())
        update_applicant_status(self.request('Hired'), 'application')
        send.assert_not_called()

    @patch('employers.notifications.send_mail')
    @patch('employers.views.db')
    def test_failed_decision_save_does_not_send_email(self, db, send):
        ref = self.application(db)
        ref.update.side_effect = OSError('unavailable')
        update_applicant_status(self.request(), 'application')
        send.assert_not_called()

    @patch('employers.notifications.send_mail', side_effect=OSError('unavailable'))
    @patch('employers.views.db')
    def test_failed_email_keeps_decision_and_can_be_retried(self, db, send):
        ref = self.application(db)
        request = self.request()
        update_applicant_status(request, 'application')
        self.assertEqual(ref.update.call_args.args[0]['status'], 'Accepted')
        self.assertNotIn('acceptance_email_sent_at', ref.update.call_args.args[0])
        self.assertTrue(any('Decision saved, but' in str(message) for message in request._messages))
        self.application(db, status='Accepted', candidate_message='Please contact us for your start date.')
        send.side_effect = None
        send.return_value = 1
        update_applicant_status(self.request(), 'application')
        self.assertIn('acceptance_email_sent_at', ref.update.call_args.args[0])

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD='')
    @patch('employers.notifications.send_mail')
    @patch('employers.views.db')
    def test_missing_configuration_is_reported_without_claiming_delivery(self, db, send):
        self.application(db)
        request = self.request()
        update_applicant_status(request, 'application')
        send.assert_not_called()
        self.assertTrue(any('configure the email provider and sender account' in str(message) for message in request._messages))

    @patch('employers.notifications.send_mail')
    @patch('employers.views.db')
    def test_invalid_recipient_is_not_sent(self, db, send):
        self.application(db, applicant_email='not-an-email')
        update_applicant_status(self.request(), 'application')
        send.assert_not_called()

    def test_removed_notification_panel_is_not_in_dashboard_or_tracker(self):
        from django.template.loader import get_template
        for name in ('dashboard', 'application_tracker'):
            template = get_template(f'jobseekers/{name}.html')
            self.assertNotIn('includes/application_updates.html', template.template.source)
