from servinn_core.moderation import RespectfulTextFormMixin
from django import forms
from django.utils import timezone


class CandidateDecisionForm(RespectfulTextFormMixin, forms.Form):
    status = forms.ChoiceField(choices=[(s, s) for s in (
        'Reviewed', 'Shortlisted', 'Interview Invitation', 'Accepted', 'Rejected', 'Hired')])
    candidate_message = forms.CharField(max_length=1500, required=False)
    interview_at = forms.DateTimeField(required=False)
    interview_location = forms.CharField(max_length=500, required=False)

    def clean(self):
        data = super().clean()
        if data.get('status') == 'Interview Invitation':
            if not data.get('interview_at') or data['interview_at'] <= timezone.now():
                self.add_error('interview_at', 'Choose a future interview date and time.')
            if not data.get('interview_location'):
                self.add_error('interview_location', 'Enter the interview address or meeting link.')
        else:
            data['interview_at'] = None
            data['interview_location'] = ''
        return data
