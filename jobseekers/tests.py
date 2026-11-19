from unittest.mock import patch

from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from .views import profile_setup


class ProfileSettingsTests(SimpleTestCase):
    def test_custom_skills_are_saved_with_selected_skills(self):
        request = self.request({'first_name': 'Ana', 'last_name': 'Reyes',
                                'skills': ['Tutor', 'Other'], 'other_skills': 'Sewing, Baking'})
        self.assertEqual(profile_setup(request).url, reverse('profile_setup'))
        payload = self.document.update.call_args.args[0]
        self.assertEqual(payload['skills'], ['Tutor', 'Sewing', 'Baking'])
        self.assertNotIn('other_skills', payload)

    def test_empty_other_description_prevents_save(self):
        response = profile_setup(self.request({'first_name': 'Ana', 'last_name': 'Reyes',
                                               'skills': ['Other'], 'other_skills': ''}))
        self.assertContains(response, 'Please specify your other skills.')
        self.document.update.assert_not_called()

    def test_multiple_checked_skills_are_saved(self):
        request = self.request({'first_name': 'Ana', 'last_name': 'Reyes',
                                'skills': ['Nanny', 'Tutor', 'Tubero']})
        self.assertEqual(profile_setup(request).url, reverse('profile_setup'))
        self.assertEqual(self.document.update.call_args.args[0]['skills'], ['Nanny', 'Tutor', 'Tubero'])

    def test_unchecking_all_skills_clears_saved_selection(self):
        request = self.request({'first_name': 'Ana', 'last_name': 'Reyes'})
        self.assertEqual(profile_setup(request).url, reverse('profile_setup'))
        self.assertEqual(self.document.update.call_args.args[0]['skills'], [])

    def test_skills_field_includes_choices_without_separate_category(self):
        response = profile_setup(self.request())
        self.assertContains(response, 'type="checkbox" name="skills"')
        self.assertContains(response, 'value="Nanny"')
        self.assertContains(response, 'value="Tutor"')
        self.assertContains(response, 'value="Tubero"')
        self.assertNotContains(response, 'name="category_preference"')

    def setUp(self):
        self.factory = RequestFactory()
        self.data = {
            'first_name': 'Ana', 'last_name': 'Reyes',
            'email': 'ana@example.com', 'skills': ['Python', 'Django'],
            'profile_completed': True, 'verified': True,
            'profile_photo': 'existing-photo',
        }
        self.db_patch = patch('jobseekers.views.db')
        self.db = self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.document = self.db.collection.return_value.document.return_value
        self.document.get.return_value.exists = True
        self.document.get.return_value.to_dict.return_value = self.data

    def request(self, data=None):
        request = (self.factory.get('/jobseeker/profile-setup/') if data is None
                   else self.factory.post('/jobseeker/profile-setup/', data))
        request.session = {'user_email': 'ana@example.com', 'user_role': 'job_seeker'}
        request._messages = FallbackStorage(request)
        return request

    def test_existing_details_render(self):
        response = profile_setup(self.request())
        self.assertContains(response, 'value="Ana"')
        self.assertContains(response, 'value="Python"')
        self.assertContains(response, 'value="Django"')
        self.assertContains(response, 'Save Changes')

    def test_save_updates_session_and_preserves_protected_fields(self):
        request = self.request({'first_name': 'Anna', 'last_name': 'Reyes',
                                'skills': ' Python, Django, ', 'role': 'admin',
                                'email': 'someone@example.com'})
        response = profile_setup(request)
        self.assertEqual(response.url, reverse('profile_setup'))
        update = self.document.update.call_args.args[0]
        self.assertEqual(update['skills'], ['Python', 'Django'])
        self.assertEqual(request.session['user_name'], 'Anna Reyes')
        for field in ('email', 'role', 'verified', 'profile_completed', 'profile_photo'):
            self.assertNotIn(field, update)
        self.db.collection.return_value.document.assert_called_with('ana@example.com')

    def test_invalid_input_does_not_save(self):
        response = profile_setup(self.request({'first_name': '', 'last_name': 'Reyes'}))
        self.assertContains(response, 'This field is required.')
        self.document.update.assert_not_called()

    def test_failed_save_keeps_entered_details(self):
        self.document.update.side_effect = RuntimeError('unavailable')
        response = profile_setup(self.request({'first_name': 'Anna', 'last_name': 'Reyes'}))
        self.assertContains(response, 'Unable to save your profile.')
        self.assertContains(response, 'value="Anna"')

    def test_anonymous_request_cannot_access_profile(self):
        request = self.request()
        request.session.clear()
        self.assertEqual(profile_setup(request).status_code, 302)
        self.document.get.assert_not_called()

    def test_incomplete_profile_still_requires_verification_setup(self):
        self.data['profile_completed'] = False
        self.assertEqual(profile_setup(self.request()).url, reverse('create_profile'))
        self.document.update.assert_not_called()
