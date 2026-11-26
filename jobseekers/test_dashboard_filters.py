from unittest.mock import Mock, patch
from django.test import SimpleTestCase,RequestFactory
from django.http import HttpResponse
from jobseekers.views import dashboard

class DashboardFilterTests(SimpleTestCase):
 def run_filters(self,query):
  records=[dict(id='one',title='Nanny',location='Iloilo',job_type='Full-time',salary_amount='10000',pay_period='Monthly',experience_years='1'),dict(id='two',title='Tutor',location='Iloilo',job_type='Contract',salary_amount=500, pay_period='Daily',experience_years=0),dict(id='three',title='Nanny',location='Manila',job_type='Part-time',salary_amount=20000,pay_period='Monthly',experience_years=3),dict(id='bad',title='Nanny',location='Iloilo',job_type='Full-time',salary_amount='NaN',pay_period='Monthly',experience_years=None)]
  snapshots=[]
  for item in records:
   snap=Mock(id=item['id']);snap.to_dict.return_value=dict(item,status='Active',review_status='Approved');snapshots.append(snap)
  posts=Mock();posts.where.return_value.stream.return_value=snapshots
  users=Mock();users.document.return_value.get.return_value.to_dict.return_value={'profile_completed':True}
  apps=Mock();apps.where.return_value.stream.return_value=[]
  saved=Mock();saved.where.return_value.stream.return_value=[]
  database=Mock();database.collection.side_effect=lambda name:{'users':users,'job_postings':posts,'applications':apps,'saved_jobs':saved}[name]
  request=RequestFactory().get('/',query);request.session={'user_role':'job_seeker','user_email':'seeker@example.com'}
  with patch('jobseekers.views.db',database),patch('jobs.matching_algorithm.score_job',return_value={'match_score':50}),patch('jobs.ratings.rating_summary',return_value={}),patch('jobseekers.views.render',return_value=HttpResponse()) as render:
   dashboard(request)
  return render.call_args.args[2]

 def test_combined_salary_period_experience_and_search(self):
  context=self.run_filters({'q':'Nanny','location':'Iloilo','salary_min':'10000','pay_period':'Monthly','experience':'1','job_type':['Full-time']})
  self.assertEqual([j['id'] for j in context['recommended_matches']],['one'])
  self.assertEqual(context['selected_types'],['Full-time'])
  self.assertEqual(context['salary_min'],'10000')

 def test_multiple_types_use_or_while_other_groups_use_and(self):
  context=self.run_filters({'job_type':['Full-time','Part-time'],'pay_period':'Monthly','salary_min':'10000'})
  self.assertEqual([j['id'] for j in context['recommended_matches']],['one','three'])

 def test_no_experience_requires_explicit_zero(self):
  context=self.run_filters({'experience':'0'})
  self.assertEqual([j['id'] for j in context['recommended_matches']],['two'])

 def test_empty_selection_shows_all_published_jobs(self):
  self.assertEqual(len(self.run_filters({})['recommended_matches']),4)

 def test_combination_can_return_no_results(self):
  self.assertEqual(self.run_filters({'pay_period':'Daily','salary_min':'75000'})['recommended_matches'],[])
