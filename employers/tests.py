from unittest.mock import patch, MagicMock
from django.test import SimpleTestCase, RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from django.urls import resolve, reverse
from accounts import views as account_views
from employers import views


class EmployerFlowTests(SimpleTestCase):
    def request(self, data=None):
        factory = RequestFactory()
        request = factory.get('/') if data is None else factory.post('/', data)
        request.session = {'user_email': 'company@example.com', 'user_role': 'employer'}
        request._messages = FallbackStorage(request)
        return request

    def test_setup_route_uses_shared_handler(self):
        self.assertEqual(resolve(reverse('create_profile')).func, account_views.create_profile)

    @patch('accounts.uploads.save_upload', return_value={'path': 'test', 'name': 'test', 'content_type': 'image/png'})
    @patch('accounts.views.db')
    def test_setup_saves_employer_and_redirects(self, db, upload):
        doc = db.collection.return_value.document.return_value
        doc.get.return_value.to_dict.return_value = {'role': 'job_seeker', 'profile_completed': False}
        from django.core.files.uploadedfile import SimpleUploadedFile
        request = self.request({'role': 'employer', 'company_name': 'Example Company',
                                'id_type': 'Passport', 'declaration': 'on', 'user_agreement': 'on',
                                'id_number': 'TEST-ID-123', 'complete_address': 'Sample Street, Sample Barangay, Iloilo City',
                                'profile_photo': SimpleUploadedFile('photo.png', b'\x89PNG\r\n\x1a\ncontent'),
                                'id_file': SimpleUploadedFile('id.pdf', b'%PDF-1.4 content'),
                                'id_back_file': SimpleUploadedFile('id-back.pdf', b'%PDF-1.4 content'),
                                'selfie_file': SimpleUploadedFile('selfie.png', b'\x89PNG\r\n\x1a\ncontent'),
                                'first_name': 'Ana', 'last_name': 'Reyes', 'contact_number': '09123456789',
                                'email': 'other@example.com'})
        response = account_views.create_profile(request)
        self.assertEqual(response.url, reverse('employer_dashboard'))
        self.assertEqual(request.session['user_role'], 'employer')
        self.assertEqual(request.session['user_name'], 'Example Company')
        self.assertEqual(doc.update.call_args.args[0]['email'], 'company@example.com')

    @patch('accounts.views.db')
    def test_missing_company_cannot_complete_setup(self, db):
        doc = db.collection.return_value.document.return_value
        doc.get.return_value.to_dict.return_value = {'profile_completed': False}
        response = account_views.create_profile(self.request({'role': 'employer'}))
        self.assertContains(response, 'Company / business name is required.')
        doc.update.assert_not_called()

    @patch('employers.views.db')
    def test_dashboard_shows_company_data_and_empty_states(self, db):
        collection = db.collection.return_value
        collection.document.return_value.get.return_value.to_dict.return_value = {
            'profile_completed': True, 'company_name': 'Example Company'}
        collection.where.return_value.stream.return_value = []
        response = views.dashboard(self.request())
        self.assertContains(response, 'Example Company')
        self.assertContains(response, 'No jobs posted yet.')
        self.assertNotContains(response, 'ACME Enterprise')
        self.assertContains(response, reverse('post_job'))

    @patch('employers.views.db')
    def test_incomplete_employer_redirected_to_setup(self, db):
        db.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {'profile_completed': False}
        self.assertEqual(views.dashboard(self.request()).url, reverse('create_profile'))

    @patch('employers.views.db')
    def test_other_employer_cannot_change_application(self, db):
        doc = db.collection.return_value.document.return_value
        doc.get.return_value.to_dict.return_value = {'employer_email': 'other@example.com'}
        views.update_applicant_status(self.request({'status': 'Accepted'}), 'app-1')
        doc.update.assert_not_called()

class PublishedJobTests(SimpleTestCase):
    @patch('jobseekers.views.db')
    def test_published_job_appears_with_application_link(self, db):
        from unittest.mock import MagicMock
        from jobseekers.views import dashboard
        users = MagicMock()
        jobs = MagicMock()
        applications = MagicMock()
        db.collection.side_effect = lambda name: {'users': users, 'job_postings': jobs, 'applications': applications, 'saved_jobs': applications}[name]
        users.document.return_value.get.return_value.to_dict.return_value = {'profile_completed': True}
        applications.where.return_value.stream.return_value = []
        job = MagicMock()
        job.id = 'published-job-123'
        job.to_dict.return_value = {'title': 'Office Assistant', 'company_name': 'Example Company',
                                   'location': 'Manila', 'description': 'Organize office records.',
                                   'job_type': 'Full-time', 'status': 'Active', 'review_status': 'Approved'}
        jobs.where.return_value.stream.return_value = [job]
        request = RequestFactory().get('/')
        request.session = {'user_email': 'seeker@example.com', 'user_role': 'job_seeker'}
        response = dashboard(request)
        self.assertContains(response, 'Office Assistant')
        self.assertContains(response, 'Example Company')
        self.assertContains(response, 'Organize office records.')
        self.assertContains(response, reverse('apply_job', args=['published-job-123']))
        self.assertNotContains(response, 'Bright Academy Tutorial Center')
        self.assertEqual(jobs.where.call_args.kwargs['filter'].value, 'Active')
        request.GET = request.GET.copy()
        request.GET['q'] = 'unrelated search'
        self.assertNotContains(dashboard(request), 'Office Assistant')
