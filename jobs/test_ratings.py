from unittest.mock import Mock, patch
from django.test import SimpleTestCase, RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from jobs.ratings import rating_summary, rating_key
from jobseekers.views import rate_job

class RatingTests(SimpleTestCase):
    def request(self, value):
        request=RequestFactory().post('/', {'rating':value})
        request.session={'user_role':'job_seeker','user_email':'seeker'}
        request._messages=FallbackStorage(request)
        return request

    def test_summary(self):
        db=Mock(); one=Mock(id=rating_key('seeker'));two=Mock(id='other')
        one.to_dict.return_value={'value':3};two.to_dict.return_value={'value':4}
        db.collection.return_value.document.return_value.collection.return_value.stream.return_value=[one,two]
        summary=rating_summary(db,'job','seeker')
        self.assertEqual(summary['rating_average'],3.5)
        self.assertEqual(summary['rating_count'],2)
        self.assertEqual(summary['own_rating'],3)

    @patch('jobseekers.views.db')
    def test_save_replaces_same_rating(self,db):
        ref=db.collection.return_value.document.return_value
        ref.get.return_value.to_dict.return_value={'status':'Active','review_status':'Approved','employer_email':'employer'}
        rate_job(self.request('3'),'job');rate_job(self.request('5'),'job')
        for call in ref.collection.return_value.document.call_args_list:
            self.assertEqual(call.args,(rating_key('seeker'),))
        self.assertEqual(ref.collection.return_value.document.return_value.set.call_args.args[0]['value'],5)

    @patch('jobseekers.views.db')
    def test_invalid_and_self_rating(self,db):
        rate_job(self.request('6'),'job')
        db.collection.assert_not_called()
        ref=db.collection.return_value.document.return_value
        ref.get.return_value.to_dict.return_value={'status':'Active','review_status':'Approved','employer_email':'seeker'}
        rate_job(self.request('5'),'job')
        ref.collection.assert_not_called()

    def test_templates(self):
        from django.template.loader import get_template
        get_template('jobseekers/dashboard.html')
        get_template('employers/dashboard.html')
