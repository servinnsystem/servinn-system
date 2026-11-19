from django.test import SimpleTestCase, RequestFactory
from django.urls import reverse
from django.template.loader import render_to_string

from jobseekers.views import jobs_list


class LegacyRouteTests(SimpleTestCase):
    def test_legacy_dashboard_bookmarks_redirect_to_protected_routes(self):
        for old, target in (
            ('/dashboard/jobseeker/', 'jobseeker_dashboard'),
            ('/dashboard/employer/', 'employer_dashboard'),
            ('/accounts/jobseeker/dashboard/', 'jobseeker_dashboard'),
            ('/accounts/landing/', 'home'),
        ):
            with self.subTest(old=old):
                response = self.client.get(old)
                self.assertRedirects(response, reverse(target), fetch_redirect_response=False)

    def test_legacy_job_listing_preserves_filters(self):
        request = RequestFactory().get('/jobseeker/jobs/', {'q': 'Nanny', 'location': 'Iloilo'})
        request.session = {'user_role': 'job_seeker', 'user_email': 'seeker@example.com'}
        self.assertEqual(jobs_list(request).url,
                         reverse('jobseeker_dashboard') + '?q=Nanny&location=Iloilo')

    def test_job_detail_application_uses_post_and_csrf(self):
        request = RequestFactory().get('/')
        request.session = {'user_role': 'job_seeker'}
        html = render_to_string('jobs/job_detail.html', {
            'request': request, 'job': {'id': 'job-1', 'title': 'Nanny'},
            'csrf_token': 'test-token'})
        self.assertIn('method="post" action="' + reverse('apply_job', args=['job-1']) + '"', html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
