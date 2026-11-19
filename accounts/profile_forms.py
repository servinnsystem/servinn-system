from servinn_core.moderation import RespectfulTextFormMixin
from django import forms
import re
from jobs.skill_forms import SkillsField, resolve_other_skills
from jobs.categories import skill_category_choices


class VerificationForm(RespectfulTextFormMixin, forms.Form):
    role = forms.ChoiceField(choices=[('job_seeker', 'Job Seeker'), ('employer', 'Employer')])
    first_name = forms.CharField(max_length=100)
    middle_name = forms.CharField(max_length=100, required=False)
    last_name = forms.CharField(max_length=100)
    date_of_birth = forms.DateField(required=False, label='Date of birth')
    nationality = forms.CharField(max_length=100, required=False)
    company_name = forms.CharField(max_length=200, required=False)
    skills = SkillsField()
    other_skills = forms.CharField(required=False, max_length=300, label='Other skills (please specify)')
    contact_number = forms.CharField(max_length=30)
    id_type = forms.ChoiceField(choices=[(v, v) for v in ["Driver's License", 'Passport', 'UMID', 'SSS', 'PhilHealth', 'National ID']])
    id_number = forms.CharField(max_length=100, label='ID number')
    complete_address = forms.CharField(max_length=500, required=False, label='Complete address')
    street_address = forms.CharField(max_length=200, required=False, label='House number / street')
    barangay = forms.CharField(max_length=100, required=False)
    city_municipality = forms.CharField(max_length=100, required=False, label='City / municipality')
    province = forms.CharField(max_length=100, required=False)
    postal_code = forms.RegexField(r'^\d{4}$', required=False, label='Postal code',
                                   error_messages={'invalid': 'Enter a four-digit Philippine postal code.'})
    declaration = forms.BooleanField(error_messages={'required': 'Please confirm that your details and documents are accurate.'})
    user_agreement = forms.BooleanField(error_messages={'required': 'Please read and accept the SERVINN user agreement before submitting your profile.'})
    profile_photo = forms.FileField()
    id_file = forms.FileField()
    id_back_file = forms.FileField(label='Valid ID (back)')
    selfie_file = forms.FileField(label='Selfie holding valid ID')
    resume_file = forms.FileField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['skills'].choices = skill_category_choices(self.initial.get('skills'))

    def clean_contact_number(self):
        number = re.sub(r'[\s()-]', '', self.cleaned_data['contact_number'])
        if not re.fullmatch(r'(09\d{9}|\+639\d{9})', number):
            raise forms.ValidationError('Enter a Philippine mobile number such as 09123456789 or +639123456789.')
        return '+63' + number[1:] if number.startswith('0') else number

    def clean_date_of_birth(self):
        from django.utils import timezone
        value = self.cleaned_data.get('date_of_birth')
        if value and value > timezone.localdate():
            raise forms.ValidationError('Date of birth cannot be in the future.')
        return value

    def clean(self):
        cleaned = super().clean()
        address_fields = ('street_address', 'barangay', 'city_municipality', 'province', 'postal_code')
        if any(cleaned.get(name) for name in address_fields) or not cleaned.get('complete_address'):
            for name in ('barangay', 'city_municipality', 'province'):
                if not cleaned.get(name):
                    self.add_error(name, 'This address field is required.')
            address = ', '.join(cleaned.get(name, '') for name in address_fields if cleaned.get(name))
            if all(cleaned.get(name) for name in ('barangay', 'city_municipality', 'province')):
                cleaned['complete_address'] = address
            else:
                self.add_error('complete_address', 'Provide your barangay, city or municipality, and province.')
        if cleaned.get('role') != 'employer':
            resolve_other_skills(self, cleaned)
        if cleaned.get('role') == 'employer' and not cleaned.get('company_name'):
            self.add_error('company_name', 'Company / business name is required.')
        for name in ('profile_photo', 'id_file', 'id_back_file', 'selfie_file', 'resume_file'):
            upload = cleaned.get(name)
            if not upload:
                continue
            if upload.size > 5 * 1024 * 1024:
                self.add_error(name, 'Each file must be 5 MB or smaller.')
                continue
            header = upload.read(16)
            upload.seek(0)
            kind = ('image/png' if header.startswith(b'\x89PNG\r\n\x1a\n') else
                    'image/jpeg' if header.startswith(b'\xff\xd8\xff') else
                    'application/pdf' if header.startswith(b'%PDF-') else None)
            allowed = ('image/png', 'image/jpeg') if name in ('profile_photo', 'selfie_file') else ('image/png', 'image/jpeg', 'application/pdf')
            if name == 'resume_file':
                allowed = ('application/pdf',)
            from pathlib import Path
            extensions = {'image/png': ['.png'], 'image/jpeg': ['.jpg', '.jpeg'], 'application/pdf': ['.pdf']}
            if kind not in allowed or Path(upload.name).suffix.lower() not in extensions.get(kind, []):
                self.add_error(name, 'Use JPG or PNG for photos and selfies, JPG/PNG/PDF for IDs, and PDF for resumes. File contents must match the extension.')
            else:
                upload.content_type = kind
        return cleaned
