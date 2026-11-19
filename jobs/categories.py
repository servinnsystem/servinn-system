JOB_CATEGORY_CHOICES = [
    ('', ''),
    ('Nanny', 'Nanny'),
    ('Tutor', 'Tutor'),
    ('Tubero', 'Tubero (Plumber)'),
    ('Electrician', 'Electrician'),
    ('Carpenter', 'Carpenter'),
    ('Housekeeper', 'Housekeeper'),
    ('Cleaner', 'Cleaner'),
    ('Caregiver', 'Caregiver'),
    ('Driver', 'Driver'),
    ('Delivery Rider', 'Delivery Rider'),
    ('Gardener', 'Gardener'),
    ('Cook', 'Cook'),
    ('Laundry Worker', 'Laundry Worker'),
    ('Painter', 'Painter'),
    ('Welder', 'Welder'),
    ('Construction Worker', 'Construction Worker'),
    ('Security Guard', 'Security Guard'),
    ('Office Assistant', 'Office Assistant'),
    ('Other', 'Other'),
]

CATEGORY_ALIASES = {
    'Nanny': ('nanny', 'babysitter', 'yaya'),
    'Tubero': ('tubero', 'plumber', 'plumbing'),
    'Carpenter': ('carpenter', 'karpintero'),
    'Cook': ('cook', 'kusinero'),
}


def normalize_skills(values):
    if isinstance(values, str):
        values = [values]
    result = []
    for value in values or []:
        for skill in str(value).split(','):
            skill = skill.strip()
            if skill and skill not in result:
                result.append(skill)
    return result


def skill_category_choices(selected=None):
    """Offer job categories while keeping previously entered skills selectable."""
    choices = [(value, label) for value, label in JOB_CATEGORY_CHOICES if value]
    for skill in normalize_skills(selected):
        if skill not in dict(choices):
            choices.append((skill, skill))
    return choices


def category_from_skills(skills):
    """Keep older matching preferences in sync with the single skills field."""
    if isinstance(skills, str):
        skills = skills.split(',')
    for skill in skills or []:
        term = str(skill).strip().casefold()
        for value, _ in JOB_CATEGORY_CHOICES:
            if value and (term == value.casefold() or term in CATEGORY_ALIASES.get(value, ())):
                return value
    return ''
