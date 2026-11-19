from django.test import SimpleTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.profile_forms import VerificationForm


class VerificationFormTests(SimpleTestCase):
    def test_structured_address_builds_complete_address(self):
        form = self.form(complete_address='', street_address='12 Sample Street',
                         barangay='Sample Barangay', city_municipality='Iloilo City',
                         province='Iloilo', postal_code='5000', date_of_birth='2000-01-15', nationality='Filipino')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['complete_address'],
                         '12 Sample Street, Sample Barangay, Iloilo City, Iloilo, 5000')

    def test_incomplete_address_and_bad_postal_code_are_rejected(self):
        form = self.form(complete_address='', barangay='Sample Barangay', postal_code='abc')
        self.assertFalse(form.is_valid())
        self.assertIn('city_municipality', form.errors)
        self.assertIn('province', form.errors)
        self.assertIn('postal_code', form.errors)

    def test_date_of_birth_cannot_be_in_future(self):
        from datetime import timedelta
        from django.utils import timezone
        form = self.form(date_of_birth=timezone.localdate() + timedelta(days=1))
        self.assertFalse(form.is_valid())
        self.assertIn('date_of_birth', form.errors)

    def test_other_requires_a_description(self):
        form = self.form(skills=['Other'], other_skills='   ')
        self.assertFalse(form.is_valid())
        self.assertIn('Please specify your other skills.', form.errors['other_skills'])

    def test_other_saves_actual_skills_instead_of_placeholder(self):
        form = self.form(skills=['Nanny', 'Other'], other_skills=' Sewing, Computer repair, Sewing ')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['skills'], ['Nanny', 'Sewing', 'Computer repair'])

    def test_multiple_skills_are_validated_as_a_list(self):
        form = self.form(skills=['Nanny', 'Tutor', 'Tubero'])
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['skills'], ['Nanny', 'Tutor', 'Tubero'])
        self.assertFalse(self.form(skills=['Unknown option']).is_valid())

    def form(self, **changes):
        data = dict(role='job_seeker', first_name='Ana', last_name='Reyes',
                    contact_number='09123456789', id_type='Passport', id_number='TEST-ID-123',
                    complete_address='Sample Street, Sample Barangay, Iloilo City', declaration='on', user_agreement='on')
        data.update(changes)
        return VerificationForm(data, {
            'profile_photo': SimpleUploadedFile('photo.png', b'\x89PNG\r\n\x1a\ncontent'),
            'id_file': SimpleUploadedFile('id.pdf', b'%PDF-1.4 content'),
            'id_back_file': SimpleUploadedFile('id-back.pdf', b'%PDF-1.4 content'),
            'selfie_file': SimpleUploadedFile('selfie.png', b'\x89PNG\r\n\x1a\ncontent'),
        })

    def test_valid_submission_normalizes_phone(self):
        form = self.form()
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['contact_number'], '+639123456789')

    def test_bad_phone_and_privileged_role_rejected(self):
        self.assertFalse(self.form(contact_number='123', role='admin').is_valid())

    def test_declaration_and_company_required(self):
        self.assertFalse(self.form(declaration='').is_valid())
        self.assertFalse(self.form(role='employer').is_valid())

    def test_disguised_file_rejected(self):
        form = self.form()
        form.files['profile_photo'] = SimpleUploadedFile('photo.png', b'<script>bad</script>')
        self.assertFalse(form.is_valid())
        self.assertIn('profile_photo', form.errors)

    def test_missing_id_rejected(self):
        form = self.form()
        del form.files['id_file']
        self.assertFalse(form.is_valid())

    def test_identity_fields_and_uploads_are_required(self):
        for name in ('id_number', 'complete_address'):
            with self.subTest(field=name):
                form = self.form(**{name: ''})
                self.assertFalse(form.is_valid())
                self.assertIn(name, form.errors)
        for name in ('id_back_file', 'selfie_file'):
            with self.subTest(field=name):
                form = self.form()
                del form.files[name]
                self.assertFalse(form.is_valid())
                self.assertIn(name, form.errors)

    def test_selfie_must_be_an_image(self):
        form = self.form()
        form.files['selfie_file'] = SimpleUploadedFile('selfie.pdf', b'%PDF-1.4 content')
        self.assertFalse(form.is_valid())
        self.assertIn('selfie_file', form.errors)

    def test_user_agreement_is_required(self):
        form = self.form(user_agreement='')
        self.assertFalse(form.is_valid())
        self.assertIn('user_agreement', form.errors)
