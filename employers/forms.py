from servinn_core.moderation import RespectfulTextFormMixin
from django import forms


class CompanyProfileForm(RespectfulTextFormMixin, forms.Form):
    company_name = forms.CharField(max_length=200, label='Company / business name')
    industry = forms.CharField(max_length=150, help_text='For example: Retail, Construction, Food Services.')
    location = forms.CharField(max_length=200, label='City / municipality and province')
    description = forms.CharField(max_length=4000, label='About your company', widget=forms.Textarea(attrs={'rows': 6}), help_text='Describe your business, the work you do, and your team.')
    website = forms.URLField(required=False, max_length=300, help_text='Include https:// in your website address.')
    business_email = forms.EmailField(required=False, label='Business contact email')
    business_phone = forms.RegexField(regex=r'^\+?[0-9 ()-]{7,25}$', required=False, label='Business contact number', error_messages={'invalid': 'Enter a valid phone number using digits and an optional country code.'})
    company_size = forms.ChoiceField(required=False, choices=[('', 'Select company size'), ('1-10', '1–10 people'), ('11-50', '11–50 people'), ('51-200', '51–200 people'), ('201+', '201+ people')])

    def sections(self):
        return [
            {'title': 'Company essentials', 'fields': [self[name] for name in ('company_name', 'industry', 'location', 'company_size')]},
            {'title': 'Contact information', 'fields': [self[name] for name in ('business_email', 'business_phone', 'website')]},
            {'title': 'Your company story', 'fields': [self['description']]},
        ]

class JobConditionsForm(RespectfulTextFormMixin, forms.Form):
    salary_amount = forms.FloatField(required=False, min_value=0, max_value=100000000)
    pay_period = forms.ChoiceField(required=False, choices=[('', 'Not specified'), ('Hourly', 'Hourly'), ('Daily', 'Daily'), ('Monthly', 'Monthly')])
    experience_years = forms.IntegerField(required=False, min_value=0, max_value=60)

    def clean(self):
        values = super().clean()
        if values.get('salary_amount') is not None and not values.get('pay_period'):
            self.add_error('pay_period', 'Choose a pay period for the salary.')
        return values


class EditJobForm(JobConditionsForm):
    title = forms.CharField(max_length=200)
    category = forms.CharField(max_length=150)
    location = forms.CharField(max_length=200)
    required_skills = forms.CharField()
    job_type = forms.ChoiceField(choices=[(value, value) for value in ('Full-time', 'Part-time', 'Contract', 'Temporary')])
    description = forms.CharField(widget=forms.Textarea)

    def clean_required_skills(self):
        skills = [value.strip() for value in self.cleaned_data['required_skills'].split(',') if value.strip()]
        if not skills:
            raise forms.ValidationError('Enter at least one skill.')
        return skills
