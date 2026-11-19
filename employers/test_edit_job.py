from unittest.mock import Mock, patch
from django.test import SimpleTestCase, RequestFactory
from django.http import Http404
from django.contrib.messages.storage.fallback import FallbackStorage
from employers.views import edit_job

class EditJobTests(SimpleTestCase):
    def request(self, data=None):
        factory = RequestFactory()
        request = factory.post('/', data) if data is not None else factory.get('/')
        request.session = {'user_role': 'employer', 'user_email': 'owner@example.com'}
        request._messages = FallbackStorage(request)
        return request

    @patch('employers.views.db')
    def test_edit_form_and_update(self, db):
        ref = db.collection.return_value.document.return_value
        ref.get.return_value.to_dict.return_value = {'employer_email': 'owner@example.com', 'title': 'Cashier', 'required_skills': ['Sales', 'Counting']}
        response = edit_job(self.request(), 'job1')
        self.assertContains(response, 'Cashier')
        self.assertContains(response, 'Sales, Counting')
        self.assertContains(response, 'Save changes')
        data = {'title': 'Senior cashier', 'category': 'Retail', 'location': 'Iloilo', 'required_skills': 'Sales, Counting', 'job_type': 'Full-time', 'description': 'Serve customers', 'salary_amount': '15000', 'pay_period': 'Monthly', 'experience_years': '1', 'employer_email': 'attacker', 'status': 'Closed'}
        self.assertEqual(edit_job(self.request(data), 'job1').status_code, 302)
        changes = ref.update.call_args.args[0]
        self.assertEqual(changes['title'], 'Senior cashier')
        self.assertEqual(changes['salary'], 'PHP 15,000.00 / monthly')
        self.assertNotIn('employer_email', changes)
        self.assertEqual(changes['status'], 'Pending Review')
        self.assertEqual(changes['review_status'], 'Pending')
        db.collection.return_value.add.assert_not_called()

    @patch('employers.views.db')
    def test_wrong_owner_and_missing_job(self, db):
        ref = db.collection.return_value.document.return_value
        ref.get.return_value.to_dict.return_value = {'employer_email': 'other@example.com'}
        for data in (None, {'title': 'Changed'}):
            with self.assertRaises(Http404):
                edit_job(self.request(data), 'job1')
        ref.get.return_value.exists = False
        with self.assertRaises(Http404):
            edit_job(self.request(), 'missing')
        ref.update.assert_not_called()

    @patch('employers.views.db')
    def test_invalid_form_preserves_input(self, db):
        ref = db.collection.return_value.document.return_value
        ref.get.return_value.to_dict.return_value = {'employer_email': 'owner@example.com'}
        response = edit_job(self.request({'title': 'Keep this title'}), 'job1')
        self.assertContains(response, 'Keep this title')
        self.assertContains(response, 'This field is required.')
        ref.update.assert_not_called()
