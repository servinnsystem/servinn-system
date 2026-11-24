from django.test import SimpleTestCase, RequestFactory, override_settings
from django.urls import reverse, resolve
from django.template.loader import render_to_string
from accounts.privacy import privacy_policy, POLICY_VERSION


class PrivacyPolicyTests(SimpleTestCase):
    def test_public_page_explains_collection_use_sharing_and_choices_without_database_access(self):
        response = self.client.get(reverse('privacy_policy'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/privacy_policy.html')
        for content in ('What we collect', 'How your information is used', 'Who can see your information',
                        'compatibility score', 'How long information is kept', 'correction', 'deletion',
                        'Google OAuth', 'Cloud Firestore', 'password hash', 'private document storage'):
            self.assertContains(response, content)
        self.assertContains(response, POLICY_VERSION)
        self.assertNotIn('user_email', response.wsgi_request.session)

    def test_policy_is_an_explicit_public_view(self):
        self.assertEqual(resolve('/privacy-policy/').func, privacy_policy)

    @override_settings(PRIVACY_CONTACT_EMAIL='privacy@example.com', PRIVACY_CONTROLLER_NAME='Example SERVINN operator')
    def test_configured_privacy_contact_is_displayed(self):
        response = self.client.get(reverse('privacy_policy'))
        self.assertContains(response, 'mailto:privacy@example.com')
        self.assertContains(response, 'Example SERVINN operator')

    @override_settings(PRIVACY_CONTACT_EMAIL='javascript:alert(1)')
    def test_invalid_contact_is_not_inserted_into_link(self):
        response = self.client.get(reverse('privacy_policy'))
        self.assertNotContains(response, 'javascript:alert(1)')
        self.assertContains(response, 'support channel')

    def test_policy_links_available_before_data_entry(self):
        for url in ('register', 'login'):
            response = self.client.get(reverse(url))
            self.assertContains(response, reverse('privacy_policy'))
        request = RequestFactory().get('/')
        request.session = {'user_role': 'job_seeker', 'user_email': 'seeker@example.com'}
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()
        for template in ('accounts/create_profile.html', 'accounts/user_agreement.html',
                         'jobseekers/profile_setup.html', 'jobseekers/documents.html', 'jobseekers/dashboard.html'):
            with self.subTest(template=template):
                html = render_to_string(template, {'request': request})
                self.assertIn('href="' + reverse('privacy_policy') + '"', html)

    def test_policy_does_not_promise_automatic_data_removal(self):
        response = self.client.get(reverse('privacy_policy'))
        self.assertContains(response, 'does not currently apply a fixed automatic deletion period')
        self.assertContains(response, 'does not automatically delete')

    def test_privacy_endpoint_is_read_only(self):
        self.assertEqual(self.client.post(reverse('privacy_policy')).status_code, 405)
