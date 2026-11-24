from servinn_core.firestore_config import FieldFilter
from jobs.publication import is_published
# jobs/views.py
from django.shortcuts import render, redirect # type: ignore
from django.contrib import messages # type: ignore
from accounts.decorators import role_required
from servinn_core.firestore_config import db # type: ignore
from .matching_algorithm import generate_smart_matches
from .location_engine import filter_jobs_by_proximity


def _employer_for_job(job_id):
    """Resolve an employer through an available posting, without exposing documents."""
    from django.http import Http404
    posting = db.collection('job_postings').document(job_id).get()
    job = posting.to_dict() if posting.exists else {}
    if not is_published(job) or not job.get('employer_email'):
        raise Http404('Employer profile not available.')
    snapshot = db.collection('users').document(job['employer_email']).get()
    employer = snapshot.to_dict() if snapshot.exists else {}
    if employer.get('role') != 'employer':
        raise Http404('Employer profile not available.')
    return job, employer


@role_required(allowed_roles=['job_seeker'])
def employer_profile(request, job_id):
    from .employer_profiles import public_employer_profile
    job, employer = _employer_for_job(job_id)
    # Pass only the fields intended for job seekers; identity documents remain private.
    profile = public_employer_profile(employer, job)
    response = render(request, 'jobs/employer_profile.html', {
        'employer_profile': profile, 'job_id': job_id, 'job_title': job.get('title', '')})
    response['Cache-Control'] = 'private, no-store'
    return response


@role_required(allowed_roles=['job_seeker'])
def employer_photo(request, job_id):
    from django.http import FileResponse, Http404
    from accounts.uploads import private_storage
    _, employer = _employer_for_job(job_id)
    metadata = employer.get('profile_photo_file') or {}
    if not metadata.get('path') or metadata.get('content_type') not in ('image/jpeg', 'image/png'):
        raise Http404('Profile photo not available.')
    try:
        response = FileResponse(private_storage.open(metadata['path'], 'rb'),
                                content_type=metadata['content_type'])
    except FileNotFoundError:
        raise Http404('Profile photo not available.')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response

def job_search(request):
    """Search real, approved postings with working filters and sorting."""
    from datetime import datetime
    from .categories import normalize_skills
    from math import isfinite
    keyword = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()
    location_filter = request.GET.get('location', '').strip()
    selected_type = request.GET.get('job_type', '')
    sort = request.GET.get('sort', 'latest')
    sort = sort if sort in ('latest', 'title') else 'latest'
    job_types = ('Full-time', 'Part-time', 'Contract', 'Temporary')
    selected_type = selected_type if selected_type in job_types else ''
    all_jobs = []
    for document in db.collection('job_postings').where(filter=FieldFilter('status', '==', 'Active')).stream():
        job = document.to_dict()
        if not is_published(job):
            continue
        job['id'] = document.id
        text = ' '.join(str(job.get(field) or '') for field in ('title', 'description', 'company_name', 'category'))
        text += ' ' + ' '.join(normalize_skills(job.get('required_skills')))
        if keyword.casefold() not in text.casefold():
            continue
        if category_filter.casefold() not in str(job.get('category') or '').casefold():
            continue
        if location_filter.casefold() not in str(job.get('location') or '').casefold():
            continue
        if selected_type and job.get('job_type') != selected_type:
            continue
        posted = job.get('published_at') or job.get('created_at') or getattr(document, 'create_time', None)
        job['posted_at'] = posted if isinstance(posted, datetime) else None
        all_jobs.append(job)
    lat, lon = request.GET.get('lat'), request.GET.get('lon')
    if lat and lon:
        try:
            lat, lon = float(lat), float(lon)
            if isfinite(lat) and isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
                all_jobs = filter_jobs_by_proximity(lat, lon, all_jobs)
        except (TypeError, ValueError):
            pass
    if sort == 'title':
        all_jobs.sort(key=lambda job: str(job.get('title') or '').casefold())
    else:
        all_jobs.sort(key=lambda job: job['posted_at'].timestamp() if job['posted_at'] else 0, reverse=True)
    return render(request, 'jobs/job_search.html', {
        'jobs': all_jobs, 'keyword': keyword, 'category_filter': category_filter,
        'location_filter': location_filter, 'job_types': job_types, 'selected_type': selected_type, 'sort': sort})

@role_required(allowed_roles=['job_seeker'])
def job_recommendations(request):
    """
    Serves personalized, smart cross-matched recommendations 
    tailored to the candidate's skills and experience.
    """
    seeker_email = request.session.get('user_email')
    recommended_jobs = generate_smart_matches(seeker_email)

    return render(request, 'jobs/job_search.html', {
        'jobs': recommended_jobs,
        'is_recommendation_page': True
    })

def job_detail(request, job_id):
    """Displays detailed specification for a selected job posting."""
    job_ref = db.collection('job_postings').document(job_id).get()

    if not job_ref.exists:
        messages.error(request, "Job posting not found.")
        return redirect('job_search')

    job_data = job_ref.to_dict()
    if not is_published(job_data):
        from django.http import Http404
        raise Http404('Published job not found.')
    job_data['id'] = job_ref.id

    # Check if logged-in job seeker has already applied to this post
    user_email = request.session.get('user_email')
    already_applied = False
    
    if user_email and request.session.get('user_role') == 'job_seeker':
        existing_app = db.collection('applications')\
            .where(filter=FieldFilter('job_id', '==', job_id))\
            .where(filter=FieldFilter('applicant_email', '==', user_email)).get()
        already_applied = len(existing_app) > 0

    return render(request, 'jobs/job_detail.html', {
        'job': job_data,
        'already_applied': already_applied
    })
