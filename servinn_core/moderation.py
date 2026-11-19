"""Local, deterministic filtering for user-visible text; credentials are excluded."""
import re
import unicodedata
from django.core.exceptions import ValidationError

MESSAGE = 'Please remove profanity, abusive language, or threats before submitting.'
# Whole words only: do not match short fragments inside names or occupations.
BLOCKED_TERMS = (
    'fuck', 'fucking', 'fucker', 'motherfucker', 'shit', 'bullshit', 'asshole',
    'bitch', 'bastard', 'cunt', 'putangina', 'putang ina', 'tangina', 'puta',
    'gago', 'gaga', 'tanga', 'ulol', 'yawa', 'buang', 'pisti', 'piste',
    'bilat', 'burat', 'i will kill you', 'i will hurt you', 'kill yourself',
    'papatayin kita', 'patyon taka',
)
TEXT_FIELDS = frozenset((
    'first_name', 'middle_name', 'last_name', 'full_name', 'company_name',
    'industry', 'location', 'description', 'title', 'category', 'required_skills',
    'skills', 'other_skills', 'education', 'experience', 'about_me', 'barangay',
    'languages', 'certifications', 'preferred_work_location', 'nationality',
    'complete_address', 'street_address', 'city_municipality', 'province',
    'candidate_message', 'interview_location', 'admin_notes', 'review_note',
))
TRANSLATION = str.maketrans({'0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's',
                           '7': 't', '@': 'a', '$': 's'})


def normalize(value):
    value = unicodedata.normalize('NFKD', value).casefold()
    value = ''.join(c for c in value if unicodedata.category(c) not in ('Mn', 'Cf')).translate(TRANSLATION)
    value = re.sub(r'(?<=[a-z])!(?=[a-z])', 'i', value)
    return re.sub(r'([a-z])\1+', r'\1', value)


def term_pattern(term):
    # Repeated letters and separators catch e.g. f.u.c.k and shiiit.
    return r'(?<!\w)' + r'[\W_]*'.join(re.escape(c) for c in normalize(term) if c != ' ') + r'(?!\w)'


PATTERNS = tuple(re.compile(term_pattern(term)) for term in BLOCKED_TERMS)


def validate_respectful_text(value):
    if isinstance(value, (list, tuple)):
        for item in value:
            validate_respectful_text(item)
    elif isinstance(value, str):
        normalized = normalize(value)
        if any(pattern.search(normalized) for pattern in PATTERNS):
            raise ValidationError(MESSAGE, code='abusive_language')


class RespectfulTextFormMixin:
    def clean(self):
        values = super().clean()
        for name in tuple(values):
            if name in TEXT_FIELDS:
                try:
                    validate_respectful_text(values[name])
                except ValidationError as error:
                    self.add_error(name, error)
        return values
