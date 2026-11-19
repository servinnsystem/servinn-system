from jobs.publication import is_published
# jobs/matching_algorithm.py
from servinn_core.firebase_config import db # type: ignore
from difflib import SequenceMatcher
import re

def calculate_jaccard_similarity(set_a, set_b):
    """Calculates Jaccard overlap index between two skill sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = set_a.intersection(set_b)
    union = set_a.union(set_b)
    return len(intersection) / len(union)


def generate_smart_matches(seeker_email):
    """
    Queries Firestore to fetch applicant data and calculates cross-match score
    against all active job postings in the database.
    """
    user_doc = db.collection('users').document(seeker_email).get()
    if not user_doc.exists:
        return []

    seeker = user_doc.to_dict()
    seeker_skills = set([s.lower() for s in seeker.get('skills', [])])
    seeker_category = seeker.get('category_preference', '').lower()

    jobs_ref = db.collection('job_postings').where('status', '==', 'Active').stream()
    matched_results = []

    for job in jobs_ref:
        job_data = job.to_dict()
        if not is_published(job_data):
            continue
        job_data['id'] = job.id

        required_skills = set([s.lower() for s in job_data.get('required_skills', [])])
        job_category = job_data.get('category', '').lower()

        # 1. Skill Match Weight (60%)
        skill_score = calculate_jaccard_similarity(seeker_skills, required_skills) * 60

        # 2. Category Match Weight (25%)
        category_score = 25.0 if seeker_category and seeker_category == job_category else 0.0

        # 3. Baseline Experience Score (15%)
        experience_score = 15.0 if seeker.get('experience') else 5.0

        # Cumulative Match Percentage
        total_match_score = round(skill_score + category_score + experience_score, 1)

        job_data['match_score'] = total_match_score
        job_data['skill_overlap_count'] = len(seeker_skills.intersection(required_skills))

        # Include jobs with at least 15% compatibility
        if total_match_score >= 15.0:
            matched_results.append(job_data)

    # Sort descending by match score
    return sorted(matched_results, key=lambda x: x['match_score'], reverse=True)

def score_job(profile, job):
    """Explainable ranking, not an eligibility or hiring decision."""
    def skills(value):
        if isinstance(value, str):
            value = value.split(',')
        return {str(item).strip().casefold() for item in (value or []) if str(item).strip()}
    wanted = skills(job.get('required_skills'))
    overlap = wanted & skills(profile.get('skills'))
    score = 70 * len(overlap) / len(wanted) if wanted else 0
    reasons = [f'{len(overlap)} of {len(wanted)} required skills match'] if wanted else []
    # People often enter an occupation (e.g. Nanny) in Skills & Expertise.
    # Match whole title words, allowing small typos only in longer words.
    def words(value):
        return set(re.findall(r'[^\W_]+', value.casefold()))

    profile_words = set()
    for skill in skills(profile.get('skills')):
        profile_words.update(words(skill))
    from .categories import CATEGORY_ALIASES
    category = profile.get('category_preference') or ''
    if category and category != 'Other':
        for term in CATEGORY_ALIASES.get(category, (category,)):
            profile_words.update(words(term))
    title_words = words(str(job.get('title') or '')) - {
        'a', 'an', 'the', 'and', 'or', 'for', 'of', 'with', 'wanted',
        'hiring', 'needed', 'full', 'part', 'time',
    }
    def same_word(left, right):
        return left == right or (
            min(len(left), len(right)) >= 4
            and left[0] == right[0]
            and SequenceMatcher(None, left, right).ratio() >= 0.85
        )

    title_match = bool(title_words) and all(
        any(same_word(word, skill) for skill in profile_words)
        for word in title_words
    )
    if title_match:
        score = max(score, 70)
        reasons.insert(0, 'Job title matches your profile skills')
    location = str(profile.get('preferred_work_location') or profile.get('location') or '').strip().casefold()
    job_location = str(job.get('location') or '').strip().casefold()
    if location and job_location and (location in job_location or job_location in location):
        score += 20
        reasons.append('Preferred location matches')
    if profile.get('preferred_job_type') and profile['preferred_job_type'] == job.get('job_type'):
        score += 10
        reasons.append('Preferred employment type matches')
    return {'match_score': round(score), 'match_reasons': reasons,
            'title_match': title_match}
