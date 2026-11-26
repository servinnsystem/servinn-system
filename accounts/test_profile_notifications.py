from unittest.mock import Mock, patch
from django.test import SimpleTestCase, RequestFactory, override_settings
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core import mail
from admin_panel.views import update_clearance_status
from accounts.profile_notifications import send_profile_decision

class ProfileRejectionNotificationTests(SimpleTestCase):
 def request(self,status='Rejected'):
  request=RequestFactory().post('/',{'clearance_status':status,'admin_notes':'Please upload a readable ID.'})
  request.session={'user_role':'admin'}
  request.user=Mock(is_authenticated=True,is_active=True,is_superuser=True)
  request.user.get_username.return_value='reviewer'
  request._messages=FallbackStorage(request)
  return request

 @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',DEFAULT_FROM_EMAIL='sender@example.com')
 def test_email_includes_feedback_and_next_steps(self):
  send_profile_decision('applicant@gmail.com',{'first_name':'Ana'},'Please upload a readable ID.', 'Rejected')
  self.assertEqual(len(mail.outbox),1)
  self.assertEqual(mail.outbox[0].to,['applicant@gmail.com'])
  self.assertIn('Please upload a readable ID.',mail.outbox[0].body)
  self.assertIn('Documents & corrections',mail.outbox[0].body)

 @patch('accounts.profile_notifications.send_profile_decision')
 @patch('admin_panel.views.db')
 def test_notifies_only_changed_job_seeker_decisions(self,db,notify):
  ref=db.collection.return_value.document.return_value
  for role,previous,status,expected in [('job_seeker','Under Review','Rejected',True),('job_seeker','Rejected','Rejected',False),('employer','Under Review','Rejected',False),('job_seeker','Under Review','Verified',True),('job_seeker','Verified','Verified',False),('job_seeker','Rejected','Verified',True),('job_seeker','Verified','Rejected',True),('employer','Under Review','Verified',False),('job_seeker','Under Review','Correction Requested',False)]:
   notify.reset_mock()
   ref.get.return_value.to_dict.return_value={'role':role,'clearance_status':previous}
   update_clearance_status(self.request(status),'applicant@gmail.com')
   self.assertEqual(notify.called,expected)

 @patch('accounts.profile_notifications.send_profile_decision',side_effect=RuntimeError('private provider details'))
 @patch('admin_panel.views.db')
 def test_email_failure_preserves_rejection_and_warns_admin(self,db,notify):
  ref=db.collection.return_value.document.return_value
  ref.get.return_value.to_dict.return_value={'role':'job_seeker','clearance_status':'Under Review'}
  request=self.request()
  self.assertEqual(update_clearance_status(request,'applicant@gmail.com').status_code,302)
  self.assertEqual(ref.update.call_args.args[0]['clearance_status'],'Rejected')
  text=' '.join(str(message) for message in request._messages)
  self.assertIn('could not be sent',text)
  self.assertNotIn('private provider details',text)

 @patch('accounts.profile_notifications.send_profile_decision')
 @patch('admin_panel.views.db')
 def test_failed_database_save_never_sends_notification(self,db,notify):
  ref=db.collection.return_value.document.return_value
  ref.get.return_value.to_dict.return_value={'role':'job_seeker','clearance_status':'Under Review'}
  ref.update.side_effect=RuntimeError('database unavailable')
  with self.assertRaises(RuntimeError):update_clearance_status(self.request(),'applicant@gmail.com')
  notify.assert_not_called()

 @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',DEFAULT_FROM_EMAIL='sender@example.com')
 def test_verified_email_has_approval_and_application_next_steps(self):
  send_profile_decision('applicant@gmail.com',{'first_name':'Ana'},'Welcome.', 'Verified')
  self.assertEqual(len(mail.outbox),1)
  self.assertIn('verified',mail.outbox[0].subject)
  self.assertIn('approved by an administrator',mail.outbox[0].body)
  self.assertIn('apply for jobs',mail.outbox[0].body)
  self.assertNotIn('not approved',mail.outbox[0].body)
