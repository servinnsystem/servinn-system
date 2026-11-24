from html.parser import HTMLParser
from django.test import SimpleTestCase, RequestFactory
from django.template.loader import render_to_string

class ProfileStepTests(SimpleTestCase):
 def test_profile_controls_are_grouped_into_five_steps(self):
  class Groups(HTMLParser):
   def __init__(self):super().__init__();self.stack=[];self.pages=set();self.fields={}
   def handle_starttag(self,tag,attrs):
    attrs=dict(attrs)
    if tag=='section':
     self.stack.append(attrs.get('data-profile-step'))
     if self.stack[-1]:self.pages.add(self.stack[-1])
    if tag in ('input','select','textarea') and attrs.get('name') and any(self.stack):
     self.fields[attrs['name']]=next(x for x in reversed(self.stack) if x)
   def handle_endtag(self,tag):
    if tag=='section':self.stack.pop()
  parser=Groups()
  request=RequestFactory().get('/accounts/create-profile/')
  request.session={'user_email':'applicant@example.com'}
  page=render_to_string('accounts/create_profile.html',{'user_data':{},'job_categories':[('Nanny','Nanny')]},request=request)
  parser.feed(page)
  self.assertEqual(parser.stack,[])
  self.assertEqual(len(parser.pages),5)
  expected={'first_name':'Personal details','barangay':'Address','skills':'Skills and resume','profile_photo':'Identity documents','id_file':'Identity documents','declaration':'Confirmation'}
  for field,group in expected.items():self.assertEqual(parser.fields[field],group)

