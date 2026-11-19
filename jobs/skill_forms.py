from django import forms
from .categories import normalize_skills, skill_category_choices


class SkillsField(forms.MultipleChoiceField):
    def __init__(self, **kwargs):
        super().__init__(required=False, label='Skills & Expertise',
                         choices=skill_category_choices(),
                         widget=forms.CheckboxSelectMultiple(attrs={'class': 'skills-options'}),
                         help_text='Select all skills that apply.', **kwargs)

    def to_python(self, value):
        return normalize_skills(super().to_python(value))


def resolve_other_skills(form, cleaned):
    skills = cleaned.get('skills', [])
    if 'Other' in skills:
        extra = normalize_skills(cleaned.get('other_skills', ''))
        if not extra:
            form.add_error('other_skills', 'Please specify your other skills.')
        else:
            cleaned['skills'] = normalize_skills([skill for skill in skills if skill != 'Other'] + extra)
    return cleaned
