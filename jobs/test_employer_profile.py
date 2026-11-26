from unittest.mock import Mock, patch

from django.http import Http404
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from jobs.views import employer_profile, employer_photo


class EmployerProfileTests(SimpleTestCase):
    @patch('jobs.ratings.rating_summary', return_value={})
    @patch('jobseekers.views.db')
    def test_dashboard_shows_employer_above_job_title_without_profile_link(self, db, ratings):
        from jobseekers.views import dashboard
        users, jobs, applications, saved = Mock(), Mock(), Mock(), Mock()
        db.collection.side_effect = lambda name: {
            'users': users, 'job_postings': jobs, 'applications': applications, 'saved_jobs': saved}[name]
        seeker = Mock()
        seeker.get.return_value.to_dict.return_value = {'profile_completed': True}
        employer = Mock()
        employer.get.return_value.to_dict.return_value = {
            'role': 'employer', 'company_name': 'Example Company', 'full_name': 'Ana Reyes',
            'location': 'Iloilo City', 'contact_number': '09123456789'}
        users.document.side_effect = lambda email: seeker if email == 'seeker@example.com' else employer
        postings = []
        for number in range(2):
            post = Mock(id=f'job-{number}')
            post.to_dict.return_value = {'status': 'Active', 'review_status': 'Approved', 'title': 'Tubero', 'company_name': 'Example Company',
                                        'employer_email': 'employer@example.com', 'location': 'Iloilo City'}
            postings.append(post)
        jobs.where.return_value.stream.return_value = postings
        applications.where.return_value.stream.return_value = []
        saved.where.return_value.stream.return_value = []
        response = dashboard(self.request())
        for value in ('Ana Reyes', 'Iloilo City', 'tel:09123456789'):
            self.assertContains(response, value)
        self.assertNotContains(response, 'View employer profile')
        html = response.content.decode()
        self.assertLess(html.index('Ana Reyes'), html.index('<h3>Tubero</h3>'))
        self.assertEqual(sum(call.args == ('employer@example.com',) for call in users.document.call_args_list), 1)

    def request(self):
        request = RequestFactory().get('/')
        request.session = {'user_role': 'job_seeker', 'user_email': 'seeker@example.com'}
        return request

    def database(self, db, **changes):
        job = {'status': 'Active', 'review_status': 'Approved', 'employer_email': 'employer@example.com', 'title': 'Nanny'}
        employer = {'role': 'employer', 'company_name': 'Example Company',
                    'full_name': 'Ana Reyes', 'location': 'Iloilo City',
                    'business_phone': '09123456789', 'password': 'SECRET_PASSWORD',
                    'id_document_file': {'path': 'SECRET_ID_PATH'}}
        employer.update(changes)
        jobs = Mock()
        users = Mock()
        jobs.document.return_value.get.return_value.to_dict.return_value = job
        users.document.return_value.get.return_value.to_dict.return_value = employer
        db.collection.side_effect = lambda name: {'job_postings': jobs, 'users': users}[name]
        return jobs, users

    @patch('jobs.views.db')
    def test_profile_shows_employer_details_without_private_documents(self, db):
        self.database(db)
        response = employer_profile(self.request(), 'job-1')
        for value in ('Example Company', 'Ana Reyes', 'Iloilo City', '09123456789', 'tel:09123456789'):
            self.assertContains(response, value)
        for value in ('SECRET_PASSWORD', 'SECRET_ID_PATH', 'employer@example.com'):
            self.assertNotContains(response, value)
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    @patch('jobs.views.db')
    def test_contact_falls_back_to_profile_number(self, db):
        self.database(db, business_phone='', contact_number='+639198765432')
        self.assertContains(employer_profile(self.request(), 'job-1'), 'tel:+639198765432')

    @patch('jobs.views.db')
    def test_verified_badge_requires_administrator_verified_status(self, db):
        self.database(db, clearance_status='Verified', verified=True)
        self.assertContains(employer_profile(self.request(), 'job-1'), 'class="verified-badge"')
        for status, verified in [('Under Review', False), ('Rejected', False), ('Under Review', True), ('Verified', False)]:
            with self.subTest(status=status, verified=verified):
                self.database(db, clearance_status=status, verified=verified)
                self.assertNotContains(employer_profile(self.request(), 'job-1'), 'class="verified-badge"')

    @patch('jobs.views.db')
    def test_missing_information_has_honest_fallback(self, db):
        self.database(db, business_phone='', contact_number='', location='')
        response = employer_profile(self.request(), 'job-1')
        self.assertContains(response, 'Not provided')
        self.assertNotContains(response, 'href="tel:')

    @patch('jobs.views.db')
    def test_closed_or_missing_jobs_do_not_expose_profiles(self, db):
        jobs, _ = self.database(db)
        jobs.document.return_value.get.return_value.to_dict.return_value = {'status': 'Closed'}
        with self.assertRaises(Http404):
            employer_profile(self.request(), 'job-1')
        jobs.document.return_value.get.return_value.exists = False
        with self.assertRaises(Http404):
            employer_profile(self.request(), 'job-1')

    @patch('jobs.views.db')
    def test_non_employer_account_is_not_exposed(self, db):
        self.database(db, role='job_seeker')
        with self.assertRaises(Http404):
            employer_profile(self.request(), 'job-1')

    @patch('jobs.views.db')
    def test_photo_endpoint_cannot_serve_identity_document(self, db):
        self.database(db)
        with self.assertRaises(Http404):
            employer_photo(self.request(), 'job-1')

    @patch('jobs.views.db')
    @patch('accounts.uploads.private_storage')
    def test_profile_photo_is_available_to_job_seeker(self, storage, db):
        from io import BytesIO
        self.database(db, profile_photo_file={'path': 'photo-file', 'content_type': 'image/png'})
        storage.open.return_value = BytesIO(b'photo-content')
        response = employer_photo(self.request(), 'job-1')
        self.assertEqual(b''.join(response.streaming_content), b'photo-content')
        self.assertEqual(response['Content-Type'], 'image/png')
        storage.open.assert_called_once_with('photo-file', 'rb')
        response.close()

    @patch('jobs.views.db')
    def test_anonymous_viewer_is_redirected_without_database_read(self, db):
        from django.contrib.messages.storage.fallback import FallbackStorage
        request = self.request()
        request.session = {}
        request._messages = FallbackStorage(request)
        self.assertEqual(employer_profile(request, 'job-1').url, reverse('login'))
        db.collection.assert_not_called()
