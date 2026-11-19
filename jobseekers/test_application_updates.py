from unittest.mock import Mock, patch
from datetime import datetime, timezone
from django.test import SimpleTestCase, RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from jobseekers.views import application_updates
from employers.views import update_applicant_status
import json

class ApplicationUpdateTests(SimpleTestCase):
    @patch('jobseekers.views.db')
    def test_feed_is_private(self, db):
        request = RequestFactory().get('/')
        request.session = {}
        self.assertEqual(application_updates(request).status_code, 403)
        db.collection.assert_not_called()
        request.session = {'user_email':'seeker', 'user_role':'job_seeker'}
        own = Mock(id='own'); other = Mock(id='other')
        own.to_dict.return_value = {'applicant_email':'seeker', 'status':'Shortlisted', 'status_updated_at':datetime.now(timezone.utc)}
        other.to_dict.return_value = {'applicant_email':'someone-else', 'status':'Accepted', 'status_updated_at':datetime.now(timezone.utc)}
        db.collection.return_value.where.return_value.stream.return_value = [own, other]
        response = application_updates(request)
        self.assertEqual([u['id'] for u in json.loads(response.content)['updates']], ['own'])
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    @patch('employers.views.db')
    def test_shortlist_and_ownership(self, db):
        request = RequestFactory().post('/', {'status':'Shortlisted'})
        request.session = {'user_email':'owner', 'user_role':'employer'}
        request._messages = FallbackStorage(request)
        ref = db.collection.return_value.document.return_value
        ref.get.return_value.to_dict.return_value = {'employer_email':'other'}
        update_applicant_status(request, 'app')
        ref.update.assert_not_called()
        ref.get.return_value.to_dict.return_value = {'employer_email':'owner', 'status':'Application Submitted'}
        update_applicant_status(request, 'app')
        self.assertEqual(ref.update.call_args.args[0]['status'], 'Shortlisted')
        self.assertIn('status_updated_at', ref.update.call_args.args[0])
        ref.update.reset_mock()
        ref.get.return_value.to_dict.return_value = {'employer_email':'owner', 'status':'Shortlisted'}
        update_applicant_status(request, 'app')
        ref.update.assert_not_called()
