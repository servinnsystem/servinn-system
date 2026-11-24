from html.parser import HTMLParser
from django.test import SimpleTestCase, RequestFactory
from django.template.loader import render_to_string
from jobseekers.forms import ProfileSettingsForm
from employers.forms import CompanyProfileForm, EditJobForm


class LabelAudit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.labels = []
        self.active_labels = []
        self.controls = set()
        self.legends = []
        self.in_legend = False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'label':
            label = {'target': attrs.get('for'), 'nested': False, 'text': ''}
            self.labels.append(label)
            self.active_labels.append(label)
        if tag in ('input', 'select', 'textarea', 'button', 'meter', 'progress', 'output') and attrs.get('type') != 'hidden':
            if attrs.get('id'):
                self.controls.add(attrs['id'])
            for label in self.active_labels:
                label['nested'] = True
        if tag == 'legend':
            self.in_legend = True
            self.legends.append('')

    def handle_endtag(self, tag):
        if tag == 'label' and self.active_labels:
            self.active_labels.pop()
        if tag == 'legend':
            self.in_legend = False

    def handle_data(self, data):
        for label in self.active_labels:
            label['text'] += data
        if self.in_legend:
            self.legends[-1] += data


class FormLabelTests(SimpleTestCase):
    def test_rendered_profile_and_employer_labels_are_associated(self):
        request = RequestFactory().get('/')
        request.session = {'user_email': 'test@example.com', 'user_role': 'job_seeker'}
        for template, form in (('jobseekers/profile_setup.html', ProfileSettingsForm()),
                               ('accounts/create_profile.html', None),
                               ('employers/create_company.html', CompanyProfileForm()),
                               ('employers/post_job.html', EditJobForm())):
            with self.subTest(template=template):
                audit = LabelAudit()
                audit.feed(render_to_string(template, {'request': request, 'form': form, 'csrf_token': 'test-token'}))
                unassociated = [label['text'].strip() for label in audit.labels
                                if not (label['target'] in audit.controls if label['target'] else label['nested'])]
                self.assertEqual(unassociated, [])
                if template == 'jobseekers/profile_setup.html':
                    self.assertIn('Skills & Expertise', audit.legends)
