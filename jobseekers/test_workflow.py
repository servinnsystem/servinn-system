from datetime import timedelta
from unittest.mock import Mock, patch
from django.test import SimpleTestCase, RequestFactory
from django.utils import timezone
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from employers.workflow_forms import CandidateDecisionForm
from jobseekers.workflow_forms import DocumentUploadForm
from jobs.matching_algorithm import score_job
from jobseekers.views import apply_job
from employers.views import job_status
from django.http import Http404

class WorkflowTests(SimpleTestCase):
    def test_ranking(self):
        profile={'skills':['Cooking','Cleaning'], 'preferred_work_location':'Iloilo', 'preferred_job_type':'Full-time'}
        job={'required_skills':['cooking','cleaning'], 'location':'Iloilo City', 'job_type':'Full-time'}
        self.assertEqual(score_job(profile, job)['match_score'],100)
        self.assertEqual(score_job({},job)['match_score'],0)
        self.assertEqual(score_job({'skills':'COOKING'},job)['match_score'],35)

    def test_interview_validation(self):
        self.assertFalse(CandidateDecisionForm({'status':'Interview Invitation'}).is_valid())
        self.assertFalse(CandidateDecisionForm({'status':'Interview Invitation','interview_at':timezone.now()-timedelta(days=1),'interview_location':'Office'}).is_valid())
        self.assertTrue(CandidateDecisionForm({'status':'Interview Invitation','interview_at':timezone.now()+timedelta(days=1),'interview_location':'Office'}).is_valid())
        self.assertFalse(CandidateDecisionForm({'status':'Unknown'}).is_valid())

    def test_document_validation(self):
        self.assertFalse(DocumentUploadForm({},{}).is_valid())
        fake=SimpleUploadedFile('id.pdf',b'<script>bad</script>')
        self.assertFalse(DocumentUploadForm({}, {'id_document':fake}).is_valid())
        pdf=SimpleUploadedFile('resume.pdf',b'%PDF-1.4 test')
        self.assertTrue(DocumentUploadForm({}, {'resume_document':pdf}).is_valid())

    @patch('jobseekers.views.db')
    def test_unverified_cannot_apply(self, db):
        request=RequestFactory().post('/')
        request.session={'user_role':'job_seeker','user_email':'seeker'}
        request._messages=FallbackStorage(request)
        db.collection.return_value.document.return_value.get.return_value.to_dict.return_value={'clearance_status':'Under Review'}
        self.assertEqual(apply_job(request,'job').status_code,302)
        db.collection.return_value.add.assert_not_called()

    @patch('employers.views.db')
    def test_only_owner_can_archive(self,db):
        request=RequestFactory().post('/',{'status':'Archived'})
        request.session={'user_role':'employer','user_email':'owner'}
        request._messages=FallbackStorage(request)
        ref=db.collection.return_value.document.return_value
        ref.get.return_value.to_dict.return_value={'employer_email':'other'}
        with self.assertRaises(Http404): job_status(request,'job')
        ref.update.assert_not_called()
        ref.get.return_value.to_dict.return_value={'employer_email':'owner'}
        job_status(request,'job')
        ref.update.assert_called_once_with({'status':'Archived'})

    def test_templates_compile(self):
        from django.template.loader import get_template
        for name in ('jobseekers/documents.html','jobseekers/application_tracker.html','jobseekers/dashboard.html','employers/view_applicants.html','employers/dashboard.html','admin_panel/account_profile.html'):
            get_template(name)


    @patch('jobseekers.views.db')
    def test_document_page_and_empty_submission(self, db):
        from jobseekers.views import upload_documents
        db.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {
            'clearance_status': 'Correction Requested', 'admin_notes': 'Please upload a clearer ID.',
            'id_document_file': {'name': 'my-id.pdf', 'path': 'private-path'},
        }
        for method in ('get', 'post'):
            request = getattr(RequestFactory(), method)('/')
            request.session = {'user_role':'job_seeker','user_email':'seeker'}
            request._messages = FallbackStorage(request)
            response = upload_documents(request)
            self.assertContains(response, 'Please upload a clearer ID.')
            self.assertContains(response, 'Download my-id.pdf')
            self.assertContains(response, 'Your document folder')
            if method == 'post':
                self.assertContains(response, 'Choose at least one document.')
        db.collection.return_value.document.return_value.update.assert_not_called()
