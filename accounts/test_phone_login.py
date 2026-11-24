from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory
from accounts.views import phone_login

class RetiredPhoneLoginTests(SimpleTestCase):
    @patch('accounts.views.db')
    def test_old_firebase_phone_tokens_cannot_authenticate(self, db):
        request = RequestFactory().post('/accounts/phone-login/', '{"id_token":"legacy-token"}', content_type='application/json')
        request.session = {}
        self.assertEqual(phone_login(request).status_code, 410)
        self.assertNotIn('user_email', request.session)
        db.collection.assert_not_called()
