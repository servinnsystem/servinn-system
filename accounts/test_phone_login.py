import json
from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory
from django.contrib.sessions.backends.signed_cookies import SessionStore
from accounts.views import phone_login

class PhoneLoginTests(SimpleTestCase):
    def request(self, data=None):
        request = RequestFactory().post('/accounts/phone-login/', json.dumps(data or {'id_token':'token'}), content_type='application/json')
        request.session = SessionStore()
        return request

    @patch('accounts.views.db')
    @patch('firebase_admin.auth.verify_id_token')
    def test_phone_only_account(self, verify, db):
        verify.return_value = {'uid':'phone-user','phone_number':'+639123456789','firebase':{'sign_in_provider':'phone'}}
        db.collection.return_value.document.return_value.get.return_value.exists = False
        request = self.request()
        response = phone_login(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.session['user_email'], 'phone:+639123456789')
        payload = db.collection.return_value.document.return_value.create.call_args.args[0]
        self.assertEqual(payload['email'], '')
        self.assertFalse(payload['verified'])
        verify.assert_called_once_with('token', check_revoked=True)

    @patch('firebase_admin.auth.verify_id_token', side_effect=ValueError('invalid'))
    def test_invalid_token(self, verify):
        self.assertEqual(phone_login(self.request()).status_code, 401)

    @patch('firebase_admin.auth.verify_id_token')
    def test_non_phone_provider_rejected(self, verify):
        verify.return_value = {'uid':'x','phone_number':'+639123456789','firebase':{'sign_in_provider':'google.com'}}
        self.assertEqual(phone_login(self.request()).status_code, 401)

    @patch('accounts.views.db')
    @patch('firebase_admin.auth.verify_id_token')
    def test_uid_mismatch(self, verify, db):
        verify.return_value = {'uid':'x','phone_number':'+639123456789','firebase':{'sign_in_provider':'phone'}}
        db.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {'role':'job_seeker','firebase_uid':'someone-else'}
        self.assertEqual(phone_login(self.request()).status_code, 403)
