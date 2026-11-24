from jobs.publication import is_published
import base64
from django.shortcuts import render, redirect  # type: ignore
from django.contrib import messages  # type: ignore
from servinn_core.firestore_config import SERVER_TIMESTAMP, ArrayUnion  # type: ignore
from servinn_core.firestore_config import FieldFilter  # type: ignore

from accounts.decorators import role_required
from servinn_core.firestore_config import db  # type: ignore
from .forms import ProfileSettingsForm


@role_required(allowed_roles=['job_seeker'])
def rate_job(request, job_id):
    from django.http import Http404, HttpResponseNotAllowed
    from jobs.ratings import rating_key
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    value = request.POST.get('rating', '')
    if value not in ('1', '2', '3', '4', '5'):
        messages.error(request, 'Choose a rating from 1 to 5 stars.')
        return redirect('jobseeker_dashboard')
    ref = db.collection('job_postings').document(job_id)
    snapshot = ref.get()
    if not snapshot.exists or not is_published(snapshot.to_dict()):
        raise Http404('Active job not found.')
    account = request.session['user_email']
    if snapshot.to_dict().get('employer_email') == account:
        messages.error(request, 'You cannot rate your own job posting.')
        return redirect('jobseeker_dashboard')
    try:
        ref.collection('ratings').document(rating_key(account)).set({
            'value': int(value), 'updated_at': SERVER_TIMESTAMP})
    except Exception:
        messages.error(request, 'Unable to save your rating. Please try again.')
    else:
        messages.success(request, 'Your job rating has been saved. You can update it anytime.')
    return redirect('jobseeker_dashboard')


def application_updates(request):
    """Private feed of the current decisions on this job seeker's applications."""
    from django.http import JsonResponse
    email = request.session.get('user_email')
    if not email or request.session.get('user_role') != 'job_seeker':
        return JsonResponse({'error': 'Sign in as a job seeker.'}, status=403)
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required.'}, status=405)
    updates = []
    for doc in db.collection('applications').where(filter=FieldFilter('applicant_email', '==', email)).stream():
        app = doc.to_dict()
        if app.get('applicant_email') != email:
            continue
        changed = app.get('status_updated_at')
        if not changed or not hasattr(changed, 'isoformat'):
            continue
        updates.append({'id': doc.id, 'status': app.get('status', ''),
                        'title': app.get('job_title') or 'Job application',
                        'message': app.get('candidate_message', ''),
                        'interview_at': app['interview_at'].isoformat() if hasattr(app.get('interview_at'), 'isoformat') else '',
                        'interview_location': app.get('interview_location', ''),
                        'updated_at': changed.isoformat()})
    updates.sort(key=lambda item: item['updated_at'], reverse=True)
    response = JsonResponse({'updates': updates})
    response['Cache-Control'] = 'private, no-store'
    return response


def create_profile(request):
    # Keep old bookmarked setup URLs working for either account type.
    from accounts.views import create_profile as account_profile
    return account_profile(request)


@role_required(allowed_roles=['job_seeker'])
def dashboard(request):
    """Jobsora-style Job Seeker overview dashboard showing search bar, filtering, and job listings."""
    user_email = request.session.get('user_email')
    
    if not user_email:
        messages.error(request, "Session expired. Please log in again.")
        return redirect('login')

    user_doc = db.collection('users').document(user_email).get()
    user_data = user_doc.to_dict() if user_doc.exists else {}

    if not user_data or not user_data.get('profile_completed'):
        messages.warning(request, "Please complete your profile verification first.")
        return redirect('create_profile')

    # Fetch user's submitted applications
    apps_ref = db.collection('applications').where(filter=FieldFilter('applicant_email', '==', user_email)).stream()
    applications = [app.to_dict() for app in apps_ref]

    # Collect IDs of jobs already applied for
    applied_job_ids = [app.get('job_id') for app in applications if app.get('job_id')]

    # GET filter queries for Jobsora layout search
    query = request.GET.get('q', '').strip().lower()
    location_query = request.GET.get('location', '').strip().lower()

    recommended_matches = []
    for document in db.collection('job_postings').where(filter=FieldFilter('status', '==', 'Active')).stream():
        job = document.to_dict()
        if not is_published(job):
            continue
        job['id'] = document.id
        from datetime import datetime
        posted_at = job.get('published_at') or job.get('created_at') or job.get('posted_at') or getattr(document, 'create_time', None)
        job['posted_at'] = posted_at if isinstance(posted_at, datetime) else None
        from jobs.matching_algorithm import score_job
        job.update(score_job(user_data, job))
        from jobs.ratings import rating_summary
        job.update(rating_summary(db, document.id, user_email))
        job['match_stars'] = round(job['match_score'] / 20, 1)
        job['company'] = job.get('company_name', '')
        job['salary'] = job.get('salary') or 'Salary not specified'
        recommended_matches.append(job)

    recommended_matches.sort(key=lambda job: job['match_score'], reverse=True)
    saved_job_ids = [doc.to_dict().get('job_id') for doc in db.collection('saved_jobs').where(filter=FieldFilter('user_email', '==', user_email)).stream()]
    job_type = request.GET.get('job_type', '')
    selected_types = request.GET.getlist('job_type')
    salary_min = request.GET.get('salary_min', '')
    pay_period = request.GET.get('pay_period', '')
    experience = request.GET.get('experience', '')
    saved_only = request.GET.get('saved') == '1'
    hide_applied = request.GET.get('hide_applied') == '1'
    if selected_types and '' not in selected_types:
        recommended_matches = [job for job in recommended_matches if job.get('job_type') in selected_types]
    if salary_min in ('5000', '10000', '20000', '35000', '50000', '75000'):
        recommended_matches = [job for job in recommended_matches if isinstance(job.get('salary_amount'), (int, float)) and job['salary_amount'] >= int(salary_min)]
    if pay_period in ('Hourly', 'Daily', 'Monthly'):
        recommended_matches = [job for job in recommended_matches if job.get('pay_period') == pay_period]
    if experience in ('0', '1', '3', '5'):
        recommended_matches = [job for job in recommended_matches if isinstance(job.get('experience_years'), (int, float)) and (job['experience_years'] == 0 if experience == '0' else job['experience_years'] >= int(experience))]
    if saved_only:
        recommended_matches = [job for job in recommended_matches if job['id'] in saved_job_ids]
    if hide_applied:
        recommended_matches = [job for job in recommended_matches if job['id'] not in applied_job_ids]

    # Filter job cards based on search inputs
    if query:
        recommended_matches = [
            j for j in recommended_matches 
            if query in j['title'].lower() or query in j['company'].lower()
        ]
    if location_query:
        recommended_matches = [
            j for j in recommended_matches 
            if location_query in j['location'].lower()
        ]

    from jobs.employer_profiles import public_employer_profile
    employers = {}
    for job in recommended_matches:
        email = job.get('employer_email')
        if email and email not in employers:
            snapshot = db.collection('users').document(email).get()
            employer = snapshot.to_dict() if snapshot.exists else {}
            employers[email] = employer if employer.get('role') == 'employer' else {}
        job['employer_info'] = public_employer_profile(employers.get(email, {}), job)

    context = {
        'saved_job_ids': saved_job_ids, 'saved_only': saved_only, 'hide_applied': hide_applied,
        'job_type': job_type, 'job_types': ['Full-time', 'Part-time', 'Contract', 'Temporary'],
        'selected_types': selected_types, 'salary_min': salary_min, 'pay_period': pay_period, 'experience': experience,
        'salary_options': ['5000', '10000', '20000', '35000', '50000', '75000'],
        'period_options': ['Hourly', 'Daily', 'Monthly'], 'experience_options': ['0', '1', '3', '5'],
        'accepted_count': sum(app.get('status') == 'Accepted' for app in applications),
        'user_data': user_data,
        'application_count': len(applications),
        'clearance_status': user_data.get('clearance_status', 'Pending'),
        'recent_applications': applications[:5],
        'recommended_matches': recommended_matches,
        'applied_job_ids': applied_job_ids,
        'query': query,
        'location': location_query,
    }
    return render(request, 'jobseekers/dashboard.html', context)


@role_required(allowed_roles=['job_seeker'])
def profile_setup(request):
    """View and update profile details: skills, education, work experience, and job preferences."""
    user_email = request.session.get('user_email')
    if not user_email:
        return redirect('login')
        
    user_ref = db.collection('users').document(user_email)

    user_doc = user_ref.get()
    user_data = user_doc.to_dict() if user_doc.exists else {}
    if not user_data.get('profile_completed'):
        return redirect('create_profile')

    initial = dict(user_data)
    if isinstance(initial.get('skills'), list):
        initial['skills'] = ', '.join(initial['skills'])
    form = ProfileSettingsForm(request.POST if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        profile_update = dict(form.cleaned_data)
        profile_update.pop('other_skills', None)
        from jobs.categories import category_from_skills
        profile_update['category_preference'] = category_from_skills(profile_update.get('skills'))
        profile_update['full_name'] = ' '.join(
            profile_update[key] for key in ('first_name', 'middle_name', 'last_name')
            if profile_update[key]
        )
        try:
            user_ref.update(profile_update)
        except Exception:
            form.add_error(None, 'Unable to save your profile. Please try again.')
        else:
            request.session['user_name'] = profile_update['full_name']
            messages.success(request, 'Profile information updated successfully.')
            return redirect('profile_setup')
    return render(request, 'jobseekers/profile_setup.html', {'user_data': user_data, 'form': form})


@role_required(allowed_roles=['job_seeker'])
def upload_documents(request):
    """Handles upload of NBI, Police clearance, Barangay clearance, and Valid ID."""
    user_email = request.session.get('user_email')
    if not user_email:
        return redirect('login')

    from .workflow_forms import DocumentUploadForm
    from accounts.uploads import save_upload, private_storage
    ref = db.collection('users').document(user_email)
    snapshot = ref.get()
    if not snapshot.exists:
        return redirect('login')
    account = snapshot.to_dict()
    form = DocumentUploadForm(request.POST if request.method == 'POST' else None, request.FILES if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        paths = []
        try:
            updates = {}
            for name, upload in form.cleaned_data.items():
                if upload:
                    metadata = save_upload(upload)
                    from django.utils import timezone
                    metadata['uploaded_at'] = timezone.now()
                    paths.append(metadata['path'])
                    updates[name + '_file'] = metadata
            updates.update({'clearance_status': 'Under Review', 'verified': False})
            ref.update(updates)
        except Exception:
            for path in paths:
                private_storage.delete(path)
            form.add_error(None, 'Unable to save documents. Please try again.')
        else:
            messages.success(request, 'Documents submitted for administrator review.')
            return redirect('upload_documents')
    documents = [{'field': form[name], 'kind': name, 'existing': account.get(name + '_file')} for name in form.fields]
    return render(request, 'jobseekers/documents.html', {
        'form': form, 'account': account, 'documents': documents,
        'uploaded_count': sum(bool(item['existing']) for item in documents),
        'document_type_count': len(documents),
        'account_id': user_email,
    })


@role_required(allowed_roles=['job_seeker'])
def apply_job(request, job_id):
    """Submits a job application for a specific posting, mapping recommended jobs to real company names."""
    user_email = request.session.get('user_email')
    if not user_email:
        return redirect('login')

    user_doc_ref = db.collection('users').document(user_email).get()
    user_data = user_doc_ref.to_dict() if user_doc_ref.exists else {}

    if user_data.get('clearance_status') not in ['Verified', 'Approved']:
        messages.error(request, "You must complete profile verification before applying for jobs.")
        return redirect('upload_documents')

    if request.method != 'POST':
        return redirect('jobseeker_dashboard')
    job_ref = db.collection('job_postings').document(job_id).get()
    if not job_ref.exists or not is_published(job_ref.to_dict()):
        messages.error(request, 'This job is no longer available.')
        return redirect('jobseeker_dashboard')
    job_data = job_ref.to_dict()
    job_title = job_data.get('title', 'Job Position')
    company_name = job_data.get('company_name', '')
    employer_email = job_data.get('employer_email', '')

    # Check if user already applied to avoid duplicate entries
    existing_apps = db.collection('applications') \
        .where(filter=FieldFilter('applicant_email', '==', user_email)) \
        .where(filter=FieldFilter('job_id', '==', job_id)) \
        .stream()

    if any(existing_apps):
        messages.info(request, f"You have already applied for {job_title}.")
        return redirect('my_applications')

    app_data = {
        'job_id': job_id,
        'job_title': job_title,
        'company_name': company_name,
        'employer_email': employer_email,
        'applicant_email': user_email,
        'applicant_name': user_data.get('full_name', 'Job Seeker'),
        'status': 'Application Submitted',
        'status_updated_at': SERVER_TIMESTAMP,
        'applied_at': SERVER_TIMESTAMP
    }

    db.collection('applications').add(app_data)
    messages.success(request, f"Successfully applied for {job_title} at {company_name}.")
    return redirect('my_applications')


@role_required(allowed_roles=['job_seeker'])
def delete_application(request, application_id):
    """Deletes an applied job record from Firestore."""
    user_email = request.session.get('user_email')
    if not user_email:
        return redirect('login')

    if request.method == "POST":
        app_ref = db.collection('applications').document(application_id)
        app_doc = app_ref.get()

        if app_doc.exists and app_doc.to_dict().get('applicant_email') == user_email:
            app_ref.delete()
            messages.success(request, "Application successfully deleted.")
        else:
            messages.error(request, "Application not found or unauthorized access.")

    return redirect('my_applications')


@role_required(allowed_roles=['job_seeker'])
def application_tracker(request):
    """Alias view directing to my_applications."""
    return redirect('my_applications')


@role_required(allowed_roles=['job_seeker'])
def my_applications(request):
    """Displays submitted applications fetched from Firestore for the logged-in user."""
    user_email = request.session.get('user_email')
    if not user_email:
        return redirect('login')
    
    apps_ref = db.collection('applications').where(filter=FieldFilter('applicant_email', '==', user_email)).stream()
    
    applications = []
    for app in apps_ref:
        app_dict = app.to_dict()
        app_dict['id'] = app.id
        applications.append(app_dict)

    from django.core.paginator import Paginator
    statuses = ['Application Submitted', 'Reviewed', 'Shortlisted', 'Interview Invitation', 'Accepted', 'Rejected', 'Hired']
    counts = {status: sum(app.get('status') == status for app in applications) for status in statuses}
    total = len(applications)
    query = request.GET.get('q', '').strip()
    selected_status = request.GET.get('status', '')
    if query:
        applications = [app for app in applications if query.lower() in
                        ((app.get('job_title') or '') + ' ' + (app.get('company_name') or '')).lower()]
    if selected_status in statuses:
        applications = [app for app in applications if app.get('status') == selected_status]
    def applied_time(app):
        value = app.get('applied_at')
        return value.timestamp() if hasattr(value, 'timestamp') else 0
    applications.sort(key=applied_time, reverse=True)
    page = Paginator(applications, 10).get_page(request.GET.get('page'))
    filters = request.GET.copy()
    filters.pop('page', None)
    return render(request, 'jobseekers/application_tracker.html', {
        'applications': page, 'page_obj': page, 'total': total,
        'submitted': counts['Application Submitted'], 'shortlisted': counts['Shortlisted'],
        'accepted': counts['Accepted'], 'rejected': counts['Rejected'],
        'statuses': statuses, 'selected_status': selected_status, 'query': query,
        'filter_query': filters.urlencode(),
    })


@role_required(allowed_roles=['job_seeker'])
def saved_jobs(request):
    from django.urls import reverse
    return redirect(reverse('jobseeker_dashboard') + '?saved=1')


@role_required(allowed_roles=['job_seeker'])
def about_us(request):
    """Render the About Us page for job seekers."""
    user_email = request.session.get('user_email')
    if not user_email:
        return redirect('login')
        
    return render(request, 'jobseekers/about_us.html')


@role_required(allowed_roles=['job_seeker'])
def toggle_save_job(request, job_id):
    """Saves or unsaves a job posting for the logged-in user in Firestore."""
    user_email = request.session.get('user_email')
    if not user_email:
        return redirect('login')

    if request.method != 'POST':
        return redirect('jobseeker_dashboard')

    saved_ref = db.collection('saved_jobs') \
        .where(filter=FieldFilter('user_email', '==', user_email)) \
        .where(filter=FieldFilter('job_id', '==', job_id)) \
        .stream()

    existing_docs = list(saved_ref)

    if existing_docs:
        for doc in existing_docs:
            db.collection('saved_jobs').document(doc.id).delete()
        messages.success(request, "Job removed from saved list.")
    else:
        job = db.collection('job_postings').document(job_id).get()
        if not job.exists or not is_published(job.to_dict()):
            messages.error(request, 'This job is no longer available.')
            return redirect('jobseeker_dashboard')
        db.collection('saved_jobs').add({
            'user_email': user_email,
            'job_id': job_id,
            'saved_at': SERVER_TIMESTAMP
        })
        messages.success(request, "Job saved successfully.")

    return redirect('jobseeker_dashboard')


@role_required(allowed_roles=['job_seeker'])
def jobs_list(request):
    """Keep the old listing URL connected to real, personalized job results."""
    from django.urls import reverse
    destination = reverse('jobseeker_dashboard')
    if request.GET:
        destination += '?' + request.GET.urlencode()
    return redirect(destination)
