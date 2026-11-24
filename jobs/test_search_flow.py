from datetime import timedelta
from unittest.mock import Mock, patch
from django.test import SimpleTestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone
from jobs.views import job_search


class PublicSearchTests(SimpleTestCase):
    def postings(self, db):
        snapshots = []
        for key, title, role_type, skills, days in (
                ('new', 'Nanny', 'Full-time', ['Childcare'], 0),
                ('old', 'Carpenter', 'Contract', ['Woodworking'], 2)):
            snapshot = Mock(id=key)
            snapshot.to_dict.return_value = {
                'title': title, 'description': 'Local opportunity', 'required_skills': skills,
                'company_name': 'Sample Employer', 'category': 'Services', 'location': 'Iloilo',
                'job_type': role_type, 'status': 'Active', 'review_status': 'Approved',
                'published_at': timezone.now() - timedelta(days=days)}
            snapshots.append(snapshot)
        hidden = Mock(id='unreviewed')
        hidden.to_dict.return_value = {'title': 'Hidden unapproved posting', 'status': 'Active'}
        db.collection.return_value.where.return_value.stream.return_value = snapshots + [hidden]

    def request(self, **query):
        request = RequestFactory().get('/jobs/search/', query)
        request.session = {}
        return request

    @patch('jobs.views.db')
    def test_results_reach_rendered_job_cards_and_unapproved_jobs_stay_hidden(self, db):
        self.postings(db)
        response = job_search(self.request())
        self.assertContains(response, 'Nanny')
        self.assertContains(response, 'Carpenter')
        self.assertContains(response, reverse('job_detail', args=['new']))
        self.assertNotContains(response, 'Hidden unapproved posting')
        self.assertNotContains(response, 'cdn.tailwindcss.com')

    @patch('jobs.views.db')
    def test_keyword_includes_skills_and_employer_name(self, db):
        self.postings(db)
        response = job_search(self.request(q='woodworking'))
        self.assertContains(response, 'Carpenter')
        self.assertNotContains(response, '>Nanny<')
        self.assertContains(job_search(self.request(q='Sample Employer')), 'Nanny')

    @patch('jobs.views.db')
    def test_type_category_and_location_filters_work(self, db):
        self.postings(db)
        self.assertNotContains(job_search(self.request(job_type='Contract')), '>Nanny<')
        self.assertContains(job_search(self.request(job_type='Contract')), 'Carpenter')
        self.assertContains(job_search(self.request(location='Cebu')), 'No matching jobs')
        self.assertContains(job_search(self.request(category='Teaching')), 'No matching jobs')

    @patch('jobs.views.db')
    def test_sort_orders_results_and_invalid_coordinates_do_not_crash(self, db):
        self.postings(db)
        html = job_search(self.request()).content.decode()
        self.assertLess(html.index('<h2>Nanny'), html.index('<h2>Carpenter'))
        html = job_search(self.request(sort='title', lat='nan', lon='infinity')).content.decode()
        self.assertLess(html.index('<h2>Carpenter'), html.index('<h2>Nanny'))
