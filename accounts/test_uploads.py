import tempfile
from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import FileSystemStorage
from django.contrib.messages.storage.fallback import FallbackStorage
from accounts.views import create_profile, profile_file


class ProfileUploadTests(SimpleTestCase):
    def test_address_and_personal_information_are_saved(self):
        request = self.request(1)
        request.POST = request.POST.copy()
        request.POST.update({'complete_address': '', 'street_address': '12 Sample Street',
                             'barangay': 'Sample Barangay', 'city_municipality': 'Iloilo City',
                             'province': 'Iloilo', 'postal_code': '5000',
                             'date_of_birth': '2000-01-15', 'nationality': 'Filipino'})
        self.assertEqual(create_profile(request).status_code, 302)
        saved = self.doc.update.call_args.args[0]
        self.assertEqual(saved['date_of_birth'], '2000-01-15')
        self.assertEqual(saved['nationality'], 'Filipino')
        self.assertEqual(saved['city_municipality'], 'Iloilo City')
        self.assertEqual(saved['complete_address'],
                         '12 Sample Street, Sample Barangay, Iloilo City, Iloilo, 5000')

    def test_profile_creation_saves_all_checked_skills(self):
        request = self.request(1)
        request.POST = request.POST.copy()
        request.POST['role'] = 'job_seeker'
        request.POST.setlist('skills', ['Nanny', 'Tutor', 'Tubero'])
        self.assertEqual(create_profile(request).status_code, 302)
        self.assertEqual(self.doc.update.call_args.args[0]['skills'], ['Nanny', 'Tutor', 'Tubero'])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        storage_patch = patch('accounts.uploads.private_storage', FileSystemStorage(location=self.temp.name))
        self.storage = storage_patch.start()
        self.addCleanup(storage_patch.stop)
        db_patch = patch('accounts.views.db')
        self.db = db_patch.start()
        self.addCleanup(db_patch.stop)
        self.doc = self.db.collection.return_value.document.return_value
        self.doc.get.return_value.to_dict.return_value = {'profile_completed': False}

    def request(self, size):
        request = RequestFactory().post('/', {
            'role': 'employer', 'company_name': 'Example', 'first_name': 'Ana',
            'last_name': 'Reyes', 'contact_number': '09123456789', 'id_type': 'Passport', 'declaration': 'on', 'user_agreement': 'on',
            'id_number': 'TEST-ID-123', 'complete_address': 'Sample Street, Sample Barangay, Iloilo City',
            'profile_photo': SimpleUploadedFile('photo.png', b'\x89PNG\r\n\x1a\ncontent'),
            'id_back_file': SimpleUploadedFile('id-back.pdf', b'%PDF-1.4 content'),
            'selfie_file': SimpleUploadedFile('selfie.png', b'\x89PNG\r\n\x1a\ncontent'),
            'id_file': SimpleUploadedFile('id.pdf', b'%PDF-' + b'x' * size, content_type='application/pdf')})
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()
        request.session = {'user_email': 'owner@example.com', 'user_role': 'employer'}
        request._messages = FallbackStorage(request)
        return request

    def test_upload_above_old_limit_is_stored_outside_firestore(self):
        response = create_profile(self.request(300 * 1024))
        self.assertEqual(response.status_code, 302)
        payload = self.doc.update.call_args.args[0]
        self.assertNotIn('id_document', payload)
        self.assertTrue(payload['user_agreement_accepted'])
        self.assertEqual(payload['user_agreement_version'], '2026-11-14.2')
        self.assertIsNotNone(payload['user_agreement_accepted_at'])
        self.assertTrue(self.storage.exists(payload['id_document_file']['path']))
        self.assertTrue(self.storage.exists(payload['id_document_back_file']['path']))
        self.assertTrue(self.storage.exists(payload['selfie_document_file']['path']))
        self.assertEqual(payload['id_number'], 'TEST-ID-123')
        self.assertEqual(payload['complete_address'], 'Sample Street, Sample Barangay, Iloilo City')

    def test_oversized_upload_is_rejected(self):
        response = create_profile(self.request(5 * 1024 * 1024 + 1))
        self.assertContains(response, 'Each file must be 5 MB or smaller.')
        self.doc.update.assert_not_called()

    def test_no_agreement_does_not_save_profile_or_uploads(self):
        request = self.request(1)
        request.POST = request.POST.copy()
        request.POST.pop('user_agreement')
        response = create_profile(request)
        self.assertContains(response, 'Please read and accept the SERVINN user agreement')
        self.doc.update.assert_not_called()
        self.assertEqual(self.storage.listdir('')[1], [])

    def test_failed_save_cleans_uploaded_file(self):
        self.doc.update.side_effect = RuntimeError('unavailable')
        response = create_profile(self.request(300 * 1024))
        self.assertContains(response, 'Unable to save your profile.')
        self.assertEqual(self.storage.listdir('')[1], [])

    def test_other_account_cannot_read_id(self):
        request = self.request(1)
        self.assertEqual(profile_file(request, 'other@example.com', 'id_document').status_code, 403)
        for kind in ('id_document_back', 'selfie_document'):
            self.assertEqual(profile_file(request, 'other@example.com', kind).status_code, 403)
