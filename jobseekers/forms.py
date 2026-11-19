from servinn_core.moderation import RespectfulTextFormMixin
from django import forms
from jobs.categories import normalize_skills, skill_category_choices
from jobs.skill_forms import SkillsField, resolve_other_skills


class ProfileSettingsForm(RespectfulTextFormMixin, forms.Form):
    first_name = forms.CharField(max_length=100)
    middle_name = forms.CharField(max_length=100, required=False)
    last_name = forms.CharField(max_length=100)
    contact_number = forms.CharField(max_length=30, required=False)
    location = forms.CharField(max_length=200, required=False)
    skills = SkillsField()
    other_skills = forms.CharField(required=False, max_length=300, label='Other skills (please specify)',
                                  widget=forms.TextInput(attrs={'placeholder': 'For example: Sewing, Computer repair'}))
    education = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))
    experience = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4}))

    about_me = forms.CharField(max_length=1500, required=False, label='About me',
                               widget=forms.Textarea(attrs={'rows': 4}),
                               help_text='Introduce your strengths and the kind of work you enjoy.')
    barangay = forms.CharField(max_length=100, required=False)
    languages = forms.CharField(max_length=200, required=False,
                                help_text='For example: Filipino, English, Cebuano.')
    certifications = forms.CharField(max_length=2000, required=False,
                                    widget=forms.Textarea(attrs={'rows': 3}),
                                    help_text='Include relevant training, certificates or licenses, such as TESDA qualifications.')
    preferred_job_type = forms.ChoiceField(required=False, label='Preferred employment type', choices=[
        ('', 'No preference'), ('Full-time', 'Full-time'), ('Part-time', 'Part-time'), ('Contract', 'Contract')])
    preferred_work_location = forms.CharField(max_length=200, required=False,
                                            help_text='City or municipality where you would like to work.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['skills'] = normalize_skills(self.initial.get('skills'))
        self.fields['skills'].choices = skill_category_choices(self.initial['skills'])
        for name, field in self.fields.items():
            if name != 'skills':
                field.widget.attrs['class'] = 'form-control'

    def sections(self):
        groups = [
            ('Personal details', 'Your name and contact information.', ['first_name', 'middle_name', 'last_name', 'contact_number']),
            ('Profile', 'Help describe where you are based and what you offer.', ['location', 'barangay', 'languages', 'about_me']),
            ('Skills & experience', 'Highlight your qualifications and practical experience.', ['skills', 'education', 'experience', 'certifications']),
            ('Work preferences', 'Save your preferred employment type and place of work.', ['preferred_job_type', 'preferred_work_location']),
        ]
        return [{'title': title, 'description': description, 'fields': [self[name] for name in names]}
                for title, description, names in groups]

    def clean_skills(self):
        return self.cleaned_data['skills']

    def clean(self):
        return resolve_other_skills(self, super().clean())
