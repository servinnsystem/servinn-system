from unittest.mock import Mock, patch
from django.test import RequestFactory, SimpleTestCase
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import Http404
from django.utils import timezone
from employers.views import post_job, job_status
from admin_panel.views import manage_jobs
from jobs.publication import is_published, update_snapshot
from jobs.views import job_detail, job_search


class PublicationTests(SimpleTestCase):
    content = {'title': 'Nanny', 'category': 'Childcare', 'location': 'Iloilo',
               'required_skills': 'Childcare, Cooking', 'job_type': 'Full-time',
               'description': 'Care for children during the day.'}

    def request(self, data=None, role='employer', admin=False):
        factory = RequestFactory()
        request = factory.post('/', data) if data is not None else factory.get('/')
        request.session = {'user_role': role, 'user_email': 'owner@example.com'} if role else {}
        request._messages = FallbackStorage(request)
        request.user = Mock(is_authenticated=admin, is_active=True, is_superuser=admin)
        request.user.get_username.return_value = 'reviewer'
        return request

    def test_only_explicitly_approved_active_jobs_are_public(self):
        for status in ('Active', 'Pending Review', 'Closed', 'Archived', 'Rejected', 'Changes Requested'):
            for review in (None, 'Pending', 'Approved', 'Rejected'):
                self.assertEqual(is_published({'status': status, 'review_status': review}),
                                 status == 'Active' and review == 'Approved')

    @patch('employers.views.db')
    def test_submit_requires_authentication_and_employer_role(self, db):
        for role in (None, 'job_seeker'):
            self.assertEqual(post_job(self.request(self.content, role)).status_code, 302)
        db.collection.assert_not_called()

    @patch('employers.views.db')
    def test_profile_is_required(self, db):
        ref = db.collection.return_value.document.return_value
        for account in ({}, {'role': 'employer'}, {'role': 'job_seeker', 'profile_completed': True}):
            ref.get.return_value.to_dict.return_value = account
            self.assertEqual(post_job(self.request(self.content)).status_code, 302)
        db.collection.return_value.add.assert_not_called()

    @patch('employers.views.db')
    def test_new_job_is_pending_despite_forged_approval(self, db):
        db.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {
            'role': 'employer', 'profile_completed': True, 'company_name': 'Company'}
        data = dict(self.content, status='Active', review_status='Approved')
        self.assertEqual(post_job(self.request(data)).status_code, 302)
        job = db.collection.return_value.add.call_args.args[0]
        self.assertEqual(job['status'], 'Pending Review')
        self.assertEqual(job['review_status'], 'Pending')
        self.assertEqual(job['employer_email'], 'owner@example.com')
        self.assertFalse(is_published(job))

    @patch('employers.views.db')
    def test_invalid_submission_preserves_input_without_saving(self, db):
        db.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {
            'role': 'employer', 'profile_completed': True}
        response = post_job(self.request({'title': 'Keep this title'}))
        self.assertContains(response, 'Keep this title')
        self.assertContains(response, 'This field is required.')
        db.collection.return_value.add.assert_not_called()

    @patch('employers.views.db')
    def test_employer_cannot_publish_unapproved_job(self, db):
        ref = db.collection.return_value.document.return_value
        for review in (None, 'Pending', 'Rejected', 'Changes Requested'):
            ref.get.return_value.to_dict.return_value = {'employer_email': 'owner@example.com', 'review_status': review}
            job_status(self.request({'status': 'Active'}), 'job')
        ref.update.assert_not_called()
        ref.get.return_value.to_dict.return_value['review_status'] = 'Approved'
        job_status(self.request({'status': 'Active'}), 'job')
        ref.update.assert_called_once_with({'status': 'Active'})

    @patch('admin_panel.views.db')
    def test_non_admin_cannot_review_even_with_forged_admin_role(self, db):
        manage_jobs(self.request({'job_id': 'job', 'action': 'approve'}, role='admin'))
        db.collection.assert_not_called()

    @patch('admin_panel.views.db')
    def test_admin_approval_publishes_validated_content(self, db):
        ref = db.collection.return_value.document.return_value
        ref.get.return_value.to_dict.return_value = dict(self.content, employer_email='owner@example.com', review_status='Pending')
        manage_jobs(self.request({'job_id': 'job', 'action': 'approve'}, admin=True))
        changes = ref.update.call_args.args[0]
        self.assertTrue(is_published(changes))
        self.assertEqual(changes['reviewed_by'], 'reviewer')
        self.assertIsNotNone(changes['published_at'])

    @patch('admin_panel.views.db')
    def test_rejection_and_corrections_require_feedback(self, db):
        ref = db.collection.return_value.document.return_value
        ref.get.return_value.to_dict.return_value = dict(self.content)
        for action in ('reject', 'changes'):
            manage_jobs(self.request({'job_id': 'job', 'action': action}, admin=True))
        ref.update.assert_not_called()
        for action, expected in (('reject', 'Rejected'), ('changes', 'Changes Requested')):
            manage_jobs(self.request({'job_id': 'job', 'action': action, 'review_note': 'Clarify hours.'}, admin=True))
            changes = ref.update.call_args.args[0]
            self.assertEqual(changes['review_status'], expected)
            self.assertEqual(changes['review_note'], 'Clarify hours.')
            self.assertFalse(is_published(changes))

    @patch('admin_panel.views.db')
    def test_stale_review_or_incomplete_content_cannot_be_approved(self, db):
        ref = db.collection.return_value.document.return_value
        ref.get.return_value.to_dict.return_value = {}
        manage_jobs(self.request({'job_id': 'job', 'action': 'approve'}, admin=True))
        ref.update.assert_not_called()
        ref.get.return_value.to_dict.return_value = dict(self.content, employer_email='owner@example.com')
        ref.get.return_value.update_time = timezone.now()
        manage_jobs(self.request({'job_id': 'job', 'action': 'approve', 'version': 'old'}, admin=True))
        ref.update.assert_not_called()

    def test_update_uses_firestore_version_precondition(self):
        db, ref, snapshot = Mock(), Mock(), Mock(update_time=timezone.now())
        update_snapshot(db, ref, snapshot, {'status': 'Active'})
        db.write_option.assert_called_once_with(last_update_time=snapshot.update_time)
        ref.update.assert_called_once_with({'status': 'Active'}, option=db.write_option.return_value)

    @patch('jobs.views.db')
    def test_unapproved_active_job_is_hidden_from_search_and_direct_link(self, db):
        doc = Mock(id='job')
        doc.to_dict.return_value = dict(self.content, status='Active')
        db.collection.return_value.where.return_value.stream.return_value = [doc]
        db.collection.return_value.document.return_value.get.return_value = doc
        self.assertNotContains(job_search(self.request()), 'Nanny')
        with self.assertRaises(Http404):
            job_detail(self.request(), 'job')

    @patch('admin_panel.views.db')
    def test_review_page_displays_content_and_review_actions(self, db):
        doc = Mock(id='job')
        doc.to_dict.return_value = dict(self.content, status='Pending Review', review_status='Pending')
        db.collection.return_value.stream.return_value = [doc]
        response = manage_jobs(self.request(admin=True))
        self.assertContains(response, 'Approve &amp; publish')
        self.assertContains(response, 'Care for children during the day.')
        self.assertContains(response, 'Request corrections')
