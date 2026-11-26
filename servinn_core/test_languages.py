from html.parser import HTMLParser

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.template.loader import get_template, render_to_string
from django.test import RequestFactory, SimpleTestCase


class LanguageInputs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.codes = []
        self.ids = []
        self.pickers = 0
        self.in_picker = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if attrs.get('id') == 'language-picker':
            self.pickers += 1
            self.in_picker = True
        if tag == 'option' and self.in_picker:
            self.codes.append(attrs.get('value'))

    def handle_endtag(self, tag):
        if tag == 'select':
            self.in_picker = False


class LanguagePageTests(SimpleTestCase):
    codes = {'en', 'tl', 'hil'}

    def test_catalog_contains_three_nonempty_language_columns(self):
        source = (settings.BASE_DIR / 'static/js/language_catalog.js').read_text(encoding='utf-8')
        rows = source.split('`', 2)[1].strip().splitlines()
        for row in rows:
            if row.strip():
                with self.subTest(english=row.split('|')[0]):
                    values = row.split('|')
                    self.assertEqual(len(values), 3)
                    self.assertTrue(all(value.strip() for value in values))

    def test_all_full_page_layouts_include_shared_language_controls(self):
        roots = [settings.BASE_DIR / 'templates'] + [
            settings.BASE_DIR / app / 'templates'
            for app in ('accounts', 'jobseekers', 'employers', 'jobs', 'admin_panel')]
        for root in roots:
            for path in root.rglob('*.html'):
                source = path.read_text(encoding='utf-8-sig')
                with self.subTest(template=str(path)):
                    get_template(path.relative_to(root).as_posix())
                    if '</body>' in source:
                        self.assertEqual(source.count("include 'includes/language_picker.html'"), 1)
                        self.assertEqual(source.count("include 'includes/language_scripts.html'"), 1)
                        self.assertNotIn('class=\\"site-language-tools', source)

    def test_pages_render_one_picker_with_all_requested_languages(self):
        request = RequestFactory().get('/')
        request.session = {'user_email': 'language-test@example.com'}
        request.user = AnonymousUser()
        pages = ('landing_page.html', 'accounts/login.html', 'accounts/register.html',
                 'accounts/create_profile.html', 'jobseekers/dashboard.html',
                 'jobseekers/profile_setup.html', 'employers/dashboard.html',
                 'employers/post_job.html', 'admin_panel/login.html')
        for page in pages:
            with self.subTest(page=page):
                html = render_to_string(page, {'request': request, 'application_breakdown': [],
                                              'overview_max': 1})
                parser = LanguageInputs()
                self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'),
                                'Rendered pages must begin with the HTML doctype.')
                parser.feed(html)
                self.assertEqual(parser.pickers, 1)
                self.assertEqual(len(parser.ids), len(set(parser.ids)), 'Page contains duplicate HTML IDs.')
                self.assertEqual(set(parser.codes), self.codes)
                self.assertEqual(len(parser.codes), 3)
                self.assertEqual(html.count('/static/js/language_controller.js'), 1)
                self.assertNotIn('English fallback', html)
