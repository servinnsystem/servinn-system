from servinn_core.firestore_config import FieldFilter
from jobs.publication import is_published, pending_review, update_snapshot
# employers/views.py
from django.shortcuts import render, redirect  # type: ignore
from django.contrib import messages  # type: ignore
from django.utils import timezone
from accounts.decorators import role_required
from servinn_core.firestore_config import db  # type: ignore

@role_required(allowed_roles=['employer'])
def job_status(request, job_id):
    from django.http import Http404, HttpResponseNotAllowed
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    ref = db.collection('job_postings').document(job_id)
    snapshot = ref.get()
    if not snapshot.exists or snapshot.to_dict().get('employer_email') != request.session['user_email']:
        raise Http404
    status = request.POST.get('status')
    if status == 'Active' and snapshot.to_dict().get('review_status') != 'Approved':
        messages.error(request, 'Admin approval is required before this job can be published.')
    elif status not in ('Active', 'Closed', 'Archived'):
        messages.error(request, 'Choose a valid posting status.')
    else:
        try:
            update_snapshot(db, ref, snapshot, {'status': status})
        except Exception:
            messages.error(request, 'Unable to update this posting. Try again.')
        else:
            messages.success(request, 'Posting updated. Closed and archived jobs are hidden from job search; applications are preserved.')
    return redirect('employer_dashboard')

@role_required(allowed_roles=['employer'])
def edit_job(request, job_id):
    from django.http import Http404
    from django.utils import timezone
    from .forms import EditJobForm

    job_ref = db.collection('job_postings').document(job_id)
    snapshot = job_ref.get()
    job = snapshot.to_dict() if snapshot.exists else None
    if not job or job.get('employer_email') != request.session.get('user_email'):
        raise Http404('Job posting not found.')
    initial = dict(job)
    if isinstance(initial.get('required_skills'), list):
        initial['required_skills'] = ', '.join(initial['required_skills'])
    form = EditJobForm(request.POST if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        changes = dict(form.cleaned_data)
        amount = changes.get('salary_amount')
        changes['salary'] = f"PHP {amount:,.2f} / {changes['pay_period'].lower()}" if amount is not None else ''
        changes['updated_at'] = timezone.now()
        changes.update(pending_review())
        try:
            update_snapshot(db, job_ref, snapshot, changes)
        except Exception:
            form.add_error(None, 'Unable to save changes. Please try again.')
        else:
            messages.success(request, 'Changes submitted for admin review. This job is hidden until approved.')
            return redirect('employer_dashboard')
    return render(request, 'employers/post_job.html', {'editing': True, 'form': form, 'job_id': job_id})

@role_required(allowed_roles=['employer'])
def dashboard(request):
    """Employer dashboard showing active job postings and applicant statistics."""
    employer_email = request.session.get('user_email')

    snapshot = db.collection('users').document(employer_email).get()
    employer = snapshot.to_dict() if snapshot.exists else {}
    if not employer.get('profile_completed'):
        return redirect('create_profile')

    # Fetch total job postings created by employer
    jobs_ref = db.collection('job_postings').where(filter=FieldFilter('employer_email', '==', employer_email)).stream()
    jobs_list = [job.to_dict() | {'id': job.id} for job in jobs_ref]
    from jobs.ratings import rating_summary
    for job in jobs_list:
        job.update(rating_summary(db, job['id']))

    # Fetch total applicants received across all jobs
    apps_ref = db.collection('applications').where(filter=FieldFilter('employer_email', '==', employer_email)).stream()
    applications = [app.to_dict() for app in apps_ref]

    accepted_count = sum(app.get('status') == 'Accepted' for app in applications)
    rejected_count = sum(app.get('status') == 'Rejected' for app in applications)
    application_breakdown = [
        {'label': 'Pending / in review', 'count': len(applications) - accepted_count - rejected_count, 'color': '#b9df42'},
        {'label': 'Accepted', 'count': accepted_count, 'color': '#3e6453'},
        {'label': 'Rejected', 'count': rejected_count, 'color': '#d77b72'},
    ]
    for item in application_breakdown:
        item['percentage'] = round(item['count'] / len(applications) * 100, 1) if applications else 0

    context = {
        'application_breakdown': application_breakdown,
        'overview_max': max(len(jobs_list), len(applications), 1),
        'total_jobs': len(jobs_list),
        'total_applicants': len(applications),
        'recent_jobs': jobs_list,
        'recent_applications': applications[:5],
        'active_jobs': sum(is_published(job) for job in jobs_list),
        'shortlisted_hired': sum(app.get('status') in ('Shortlisted', 'Accepted') for app in applications),
        'company_name': employer.get('company_name') or 'Employer',
        'employer': employer
    }
    return render(request, 'employers/dashboard.html', context)

@role_required(allowed_roles=['employer'])
def create_company(request):
    """View and update detailed company profiles."""
    employer_email = request.session.get('user_email')
    emp_ref = db.collection('users').document(employer_email)

    from .forms import CompanyProfileForm
    snapshot = emp_ref.get()
    if not snapshot.exists:
        messages.error(request, 'Please sign in again to load your company account.')
        return redirect('login')
    emp_data = snapshot.to_dict()
    form = CompanyProfileForm(request.POST if request.method == 'POST' else None, initial=emp_data)
    if request.method == 'POST' and form.is_valid():
        try:
            emp_ref.update(form.cleaned_data)
        except Exception:
            form.add_error(None, 'Unable to save your company profile. Please try again.')
        else:
            request.session['user_name'] = form.cleaned_data['company_name']
            messages.success(request, 'Company profile updated successfully.')
            return redirect('create_company')
    return render(request, 'employers/create_company.html', {'emp_data': emp_data, 'form': form})


@role_required(allowed_roles=['employer'])
def post_job(request):
    """Authenticated employers submit validated content for administrator review."""
    from .forms import EditJobForm
    employer_email = request.session['user_email']
    snapshot = db.collection('users').document(employer_email).get()
    employer = snapshot.to_dict() if snapshot.exists else {}
    if employer.get('role') != 'employer':
        messages.error(request, 'Please sign in with your employer account.')
        return redirect('login')
    if not employer.get('profile_completed'):
        messages.error(request, 'Complete your employer profile before submitting a job.')
        return redirect('create_profile')
    form = EditJobForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        job_data = dict(form.cleaned_data)
        job_data.update(pending_review())
        job_data.update(employer_email=employer_email,
                        company_name=employer.get('company_name', 'Employer'),
                        created_at=timezone.now())
        amount = job_data.get('salary_amount')
        job_data['salary'] = f"PHP {amount:,.2f} / {job_data['pay_period'].lower()}" if amount is not None else ''
        try:
            db.collection('job_postings').add(job_data)
        except Exception:
            form.add_error(None, 'Unable to submit this job. Please try again.')
        else:
            messages.success(request, 'Job submitted for admin review. It will appear to job seekers only after approval.')
            return redirect('employer_dashboard')
    return render(request, 'employers/post_job.html', {'form': form})

@role_required(allowed_roles=['employer'])
def view_applicants(request):
    """Retrieves all submitted job applications for this employer."""
    employer_email = request.session.get('user_email')

    apps_ref = db.collection('applications').where(filter=FieldFilter('employer_email', '==', employer_email)).stream()
    applications = []

    for app in apps_ref:
        app_dict = app.to_dict()
        app_dict['id'] = app.id

        # Fetch candidate's current clearance status and resume link
        if not app_dict.get('applicant_email'):
            applications.append(app_dict)
            continue
        candidate_doc = db.collection('users').document(app_dict['applicant_email']).get()
        if candidate_doc.exists:
            cand_data = candidate_doc.to_dict()
            app_dict['clearance_status'] = cand_data.get('clearance_status', 'Pending')
            for field in ('location', 'skills', 'education', 'experience', 'certifications', 'contact_number'):
                app_dict[field] = cand_data.get(field, '')

        applications.append(app_dict)

    from django.core.paginator import Paginator
    statuses = ['Application Submitted', 'Reviewed', 'Shortlisted', 'Interview Invitation', 'Accepted', 'Rejected', 'Hired']
    summary = [{'status': status, 'count': sum(app.get('status') == status for app in applications)} for status in statuses]
    total = len(applications)
    query = request.GET.get('q', '').strip()
    selected_status = request.GET.get('status', '')
    if query:
        applications = [app for app in applications if query.lower() in ' '.join(str(app.get(k) or '') for k in ('applicant_name', 'applicant_email', 'job_title')).lower()]
    if selected_status in statuses:
        applications = [app for app in applications if app.get('status') == selected_status]
    applications.sort(key=lambda app: app['applied_at'].timestamp() if hasattr(app.get('applied_at'), 'timestamp') else 0, reverse=True)
    page = Paginator(applications, 10).get_page(request.GET.get('page'))
    filters = request.GET.copy()
    filters.pop('page', None)
    return render(request, 'employers/view_applicants.html', {
        'applications': page, 'page_obj': page, 'summary': summary, 'total': total,
        'query': query, 'selected_status': selected_status, 'statuses': statuses, 'filter_query': filters.urlencode(),
    })

@role_required(allowed_roles=['employer'])
def update_applicant_status(request, app_id):
    """Save an employer decision, then notify accepted applicants by email."""
    if request.method == "POST":
        new_status = request.POST.get('status')
        app_ref = db.collection('applications').document(app_id)
        
        snapshot = app_ref.get()
        if not snapshot.exists or snapshot.to_dict().get('employer_email') != request.session.get('user_email'):
            messages.error(request, 'Application not found.')
            return redirect('view_applicants')
        from .workflow_forms import CandidateDecisionForm
        form = CandidateDecisionForm(request.POST)
        if not form.is_valid():
            messages.error(request, ' '.join(str(error) for errors in form.errors.values() for error in errors))
            return redirect('view_applicants')
        from django.utils import timezone
        changes = dict(form.cleaned_data)
        current = snapshot.to_dict()
        if new_status == 'Hired' and current.get('status') not in ('Accepted', 'Hired'):
            messages.error(request, 'Accept the candidate before marking them hired.')
            return redirect('view_applicants')
        if any((current.get(key) or '') != (value or '') for key, value in changes.items()):
            changes['status_updated_at'] = timezone.now()
            event = {'status': new_status, 'at': changes['status_updated_at'],
                     'note': changes.get('candidate_message', '')}
            from servinn_core.firestore_config import SERVER_TIMESTAMP, ArrayUnion
            changes['status_history'] = ArrayUnion([event])
            try:
                update_snapshot(db, app_ref, snapshot, changes)
            except Exception:
                messages.error(request, 'Unable to save the decision. Please try again.')
                return redirect('view_applicants')
            else:
                messages.success(request, 'Candidate updated. Their application tracker will show this decision.')
        # Retry unsent acceptance emails on a repeated save without changing the decision.
        application = current | changes
        if new_status in ('Accepted', 'Hired') and not current.get('acceptance_email_sent_at'):
            from .notifications import send_acceptance_email, AcceptanceEmailError
            try:
                delivered = send_acceptance_email(app_ref, application)
            except AcceptanceEmailError as error:
                messages.warning(request, f'Decision saved, but acceptance email needs attention. {error} Save the decision again to retry.')
            else:
                if delivered:
                    messages.success(request, 'Acceptance email sent to the applicant.')


    return redirect('view_applicants')

@role_required(allowed_roles=['employer'])
def search_jobs(request):
    """Search job postings by keyword and location."""
    query = request.GET.get('q', '').strip().lower()
    location_filter = request.GET.get('location', '').strip().lower()

    jobs_ref = db.collection('job_postings').stream()
    matching_jobs = []

    for job in jobs_ref:
        job_data = job.to_dict() | {'id': job.id}
        if not is_published(job_data):
            continue

        title = job_data.get('title', '').lower()
        company_name = job_data.get('company_name', '').lower()
        description = job_data.get('description', '').lower()
        job_location = job_data.get('location', '').lower()

        # Keyword filtering
        matches_query = not query or (
            query in title or 
            query in company_name or 
            query in description
        )

        # Location filtering
        matches_location = not location_filter or (
            location_filter in job_location or 
            'remote' in job_location
        )

        if matches_query and matches_location:
            matching_jobs.append(job_data)

    context = {
        'jobs': matching_jobs,
        'query': request.GET.get('q', ''),
        'location': request.GET.get('location', ''),
    }
    return render(request, 'employers/job_list.html', context)
