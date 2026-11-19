from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import SimpleTestCase, RequestFactory
from employers.forms import EditJobForm, CompanyProfileForm
from employers.workflow_forms import CandidateDecisionForm
from accounts.profile_forms import VerificationForm
from jobseekers.forms import ProfileSettingsForm
from servinn_core.moderation import validate_respectful_text


class ModerationTests(SimpleTestCase):
    def test_profanity_threats_and_common_obfuscation_are_blocked(self):
        for value in ('FUCK', 'asshole', 'f.u.c.k', 'f u c k', 'shiiiit', 'sh1t', 'sh!t',
                      'putang ina', 'g4g0', 'buang', 'yawa', 'pisti', 'piste',
                      'I will kill you', 'papatayin kita', 'patyon taka',
                      'f\u200buck', '\uff46\uff55\uff43\uff4b', 'sh\u00edt'):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_respectful_text(value)

    def test_legitimate_names_places_and_work_terms_are_allowed(self):
        for value in ('Assistant in Scunthorpe', 'Class assistant', 'Passionate tutor',
                      'Pangasinan', 'Batangas', 'Dumangas',
                      'Install a brass fitting', 'Nanny, Cooking', 'Ana Reyes'):
            with self.subTest(value=value):
                validate_respectful_text(value)

    def test_list_values_are_checked(self):
        with self.assertRaises(ValidationError):
            validate_respectful_text(['Cooking', 'fuck'])

    def test_forms_reject_public_text_with_field_errors(self):
        for cls, field in ((EditJobForm, 'description'), (EditJobForm, 'required_skills'),
                           (CompanyProfileForm, 'description'), (CandidateDecisionForm, 'candidate_message'),
                           (VerificationForm, 'company_name'), (VerificationForm, 'other_skills'),
                           (ProfileSettingsForm, 'about_me'), (ProfileSettingsForm, 'experience')):
            with self.subTest(form=cls.__name__, field=field):
                form = cls({field: 'fuck', 'status': 'Accepted', 'role': 'employer'})
                self.assertFalse(form.is_valid())
                self.assertEqual(form.errors.as_data()[field][0].code, 'abusive_language')

    def test_clean_candidate_message_is_accepted(self):
        self.assertTrue(CandidateDecisionForm({'status': 'Accepted', 'candidate_message': 'Welcome to our team.'}).is_valid())

    def request(self, data):
        request = RequestFactory().post('/', data)
        request.session = {'user_role': 'employer', 'user_email': 'owner@example.com'}
        request._messages = FallbackStorage(request)
        return request

    @patch('employers.views.db')
    @patch('employers.notifications.send_mail')
    def test_abusive_employer_message_never_saves_or_sends(self, send, db):
        from employers.views import update_applicant_status
        ref = db.collection.return_value.document.return_value
        ref.get.return_value.to_dict.return_value = {'employer_email': 'owner@example.com'}
        update_applicant_status(self.request({'status': 'Accepted', 'candidate_message': 'You are a gago'}), 'app')
        ref.update.assert_not_called()
        send.assert_not_called()

    @patch('employers.views.db')
    def test_abusive_job_is_not_created(self, db):
        from employers.views import post_job
        db.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {
            'role': 'employer', 'profile_completed': True}
        response = post_job(self.request({'title': 'Nanny', 'category': 'Childcare', 'location': 'Iloilo',
            'required_skills': 'Cooking', 'job_type': 'Full-time', 'description': 'You are a gago'}))
        self.assertContains(response, 'Please remove profanity')
        db.collection.return_value.add.assert_not_called()

    @patch('accounts.views.db')
    def test_registration_rejects_abusive_names_but_never_scans_password(self, db):
        from accounts.views import register_seeker
        request = self.request({'first_name': 'gago', 'email': 'person@example.com', 'password': 'example-only'})
        self.assertContains(register_seeker(request), 'Please remove profanity')
        db.collection.assert_not_called()
        response = register_seeker(self.request({'first_name': 'Ana', 'email': 'person@example.com', 'password': 'fuck'}))
        self.assertEqual(response.status_code, 302)
        db.collection.return_value.document.return_value.create.assert_called_once()

    @patch('admin_panel.views.db')
    def test_abusive_admin_feedback_is_not_saved(self, db):
        from admin_panel.views import manage_jobs, update_clearance_status
        from unittest.mock import Mock
        for view, data in ((manage_jobs, {'job_id': 'job', 'action': 'reject', 'review_note': 'gago'}),
                           (update_clearance_status, {'clearance_status': 'Rejected', 'admin_notes': 'gago'})):
            request = self.request(data)
            request.user = Mock(is_authenticated=True, is_active=True, is_superuser=True)
            if view == manage_jobs:
                view(request)
            else:
                view(request, 'person@example.com')
        db.collection.assert_not_called()

    def test_browser_rules_are_rendered_as_safe_json(self):
        from django.template.loader import render_to_string
        import json
        html = render_to_string('includes/language_scripts.html')
        rules = json.loads(html.split('type="application/json">', 1)[1].split('</script>', 1)[0])
        self.assertIn('candidate_message', rules['fields'])
        self.assertNotIn('password', rules['fields'])
        self.assertNotIn('email', rules['fields'])
        self.assertIn('content_moderation.js', html)
