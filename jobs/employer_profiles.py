import re


def public_employer_profile(employer, job):
    """Only the employer fields displayed to job seekers."""
    phone = str(employer.get('business_phone') or employer.get('contact_number') or '').strip()
    full_name = employer.get('full_name') or ' '.join(
        str(employer.get(field) or '').strip()
        for field in ('first_name', 'middle_name', 'last_name')).strip()
    return {
        'company_name': employer.get('company_name') or job.get('company_name') or 'Employer',
        'name': full_name or employer.get('company_name') or 'Not provided',
        'location': employer.get('location') or 'Not provided',
        'contact_number': phone,
        'phone_link': re.sub(r'[^0-9+]', '', phone) if re.fullmatch(r'\+?[0-9 ()-]{7,25}', phone) else '',
        'description': employer.get('description') or '',
        'industry': employer.get('industry') or '',
        'has_photo': bool(employer.get('profile_photo_file')),
        'legacy_photo': employer.get('profile_photo') or '',
        'is_verified': employer.get('clearance_status') == 'Verified' and employer.get('verified') is True,
    }
