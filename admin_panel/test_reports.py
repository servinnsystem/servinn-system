from unittest.mock import Mock,patch
from datetime import datetime,timezone
from django.test import SimpleTestCase,RequestFactory
from django.http import HttpResponse
from admin_panel.views import system_reports

class ApplicationReportTests(SimpleTestCase):
 def report(self,records,query=None,render_html=False):
  request=RequestFactory().get('/portal-admin/reports/',query or {})
  request.session={'user_role':'admin','user_email':'admin@example.com'}
  request.user=Mock(is_authenticated=True,is_active=True,is_superuser=True)
  docs=[]
  for i,record in enumerate(records):
   doc=Mock(id=str(i));doc.to_dict.return_value=record;docs.append(doc)
  with patch('admin_panel.views.db') as db:
   db.collection.return_value.stream.return_value=docs
   if render_html:return system_reports(request)
   with patch('admin_panel.views.render',return_value=HttpResponse()) as render:
    response=system_reports(request)
   self.assertEqual(response['Cache-Control'],'private, no-store')
   return render.call_args.args[2]

 def test_empty_report_renders_without_division_by_zero(self):
  response=self.report([],render_html=True)
  self.assertContains(response,'No application activity yet')
  self.assertContains(response,'0.0%')

 def test_hired_count_and_unknown_status_are_included(self):
  context=self.report([{'status':'Accepted'},{'status':'Hired'},{'status':'Rejected'},{'status':'Legacy'}])
  self.assertEqual(context['placement_rate'],50.0)
  self.assertEqual(sum(item['count'] for item in context['breakdown']),4)
  self.assertEqual(context['accepted'],1)
  self.assertEqual(context['hired'],1)

 def test_filters_change_records_without_changing_totals(self):
  records=[{'status':'Accepted','job_title':'Nanny','applicant_name':'Ana'}, {'status':'Rejected','job_title':'Tutor','applicant_name':'Ben'}]
  context=self.report(records,{'q':'ana','status':'Accepted'})
  self.assertEqual(context['total_apps'],2)
  self.assertEqual(context['applications'].paginator.count,1)
  self.assertEqual(context['applications'][0]['applicant_name'],'Ana')

 def test_latest_first_pagination_and_invalid_page(self):
  records=[{'status':'Reviewed','applied_at':datetime(2026,1,day,tzinfo=timezone.utc)} for day in range(1,13)]
  context=self.report(records,{'page':'999'})
  self.assertEqual(context['applications'].number,2)
  self.assertEqual(context['applications'][0]['applied_at'].day,2)
  self.assertEqual(self.report(records)['applications'][0]['applied_at'].day,12)

 def test_invalid_status_is_ignored_and_missing_dates_supported(self):
  context=self.report([{'status':'Reviewed'},{}],{'status':'invalid'})
  self.assertEqual(context['selected_status'],'')
  self.assertEqual(len(context['applications']),2)
