from jobs.publication import is_published
# admin_panel/views.py
from django.shortcuts import render, redirect # type: ignore
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib import messages # type: ignore
from django.http import Http404
from accounts.decorators import role_required
from servinn_core.firebase_config import db # type: ignore

@role_required(allowed_roles=['admin'])
def account_profile(request, account_id):
    snapshot = db.collection('users').document(account_id).get()
    account = snapshot.to_dict() if snapshot.exists else None
    if not account or account.get('role') not in ('job_seeker', 'employer'):
        raise Http404('Account not found.')

    groups = [('Personal & contact details', [
        ('full_name', 'Full name'), ('email', 'Email address'),
        ('contact_number', 'Contact number'), ('phone_number', 'Sign-in phone'),
        ('gender', 'Gender'), ('date_of_birth', 'Date of birth'), ('nationality', 'Nationality'), ('location', 'Location')])]
    groups.append(('Address information', [('street_address', 'House number / street'),
        ('barangay', 'Barangay'), ('city_municipality', 'City / municipality'),
        ('province', 'Province'), ('postal_code', 'Postal code'), ('complete_address', 'Complete address')]))
    if account['role'] == 'employer':
        groups.append(('Company profile', [
            ('company_name', 'Business name'), ('industry', 'Industry'),
            ('company_size', 'Company size'), ('business_email', 'Business email'),
            ('business_phone', 'Business phone'), ('website', 'Website'),
            ('description', 'About the company')]))
    else:
        groups.extend([
            ('Qualifications', [('about_me', 'About me'), ('skills', 'Skills'),
             ('education', 'Education'), ('experience', 'Work experience'),
             ('certifications', 'Certifications'), ('languages', 'Languages')]),
            ('Work preferences', [('preferred_job_type', 'Employment type'),
             ('preferred_work_location', 'Preferred location')])])
    groups.append(('Identity verification', [('id_type', 'ID type'), ('id_number', 'ID number'),
                                              ('complete_address', 'Complete address')]))
    sections = []
    for title, fields in groups:
        rows = []
        for key, label in fields:
            value = account.get(key)
            if isinstance(value, list):
                value = ', '.join(str(item) for item in value)
            rows.append({'label': label, 'value': value or 'Not provided'})
        sections.append({'title': title, 'rows': rows})
    response = render(request, 'admin_panel/account_profile.html', {
        'account': account, 'account_id': account_id, 'sections': sections,
        'display_name': account.get('company_name') or account.get('full_name') or 'Account profile',
    })
    response['Cache-Control'] = 'private, no-store'
    return response

@role_required(allowed_roles=['admin'])
def dashboard(request):
    """Admin dashboard overview displaying system-wide metrics and pending verifications."""
    # Query collection metrics from Firestore
    users_ref = db.collection('users').stream()
    users_list = [u.to_dict() | {'email': u.id} for u in users_ref]
    users_list = [u for u in users_list if u.get('role') in ('job_seeker', 'employer')]

    total_seekers = sum(1 for u in users_list if u.get('role') == 'job_seeker')
    total_employers = sum(1 for u in users_list if u.get('role') == 'employer')
    pending_clearances = sum(1 for u in users_list if u.get('clearance_status') in ['Pending', 'Under Review'])

    jobs_ref = db.collection('job_postings').stream()
    jobs_list = [job.to_dict() for job in jobs_ref]
    total_jobs = len(jobs_list)

    apps_ref = db.collection('applications').stream()
    applications = [app.to_dict() for app in apps_ref]
    total_applications = len(applications)
    review_statuses = ['Pending', 'Under Review', 'Verified', 'Approved', 'Rejected', 'Correction Requested']
    verification_summary = [{'label': status, 'count': sum(u.get('clearance_status', 'Pending') == status for u in users_list)} for status in review_statuses]
    outcomes = [{'label': status, 'count': sum(app.get('status') == status for app in applications)}
                for status in ['Application Submitted', 'Shortlisted', 'Accepted', 'Rejected']]
    reviewed = [u for u in users_list if hasattr(u.get('reviewed_at'), 'timestamp')]
    reviewed.sort(key=lambda u: u['reviewed_at'].timestamp(), reverse=True)

    context = {
        'verification_summary': verification_summary, 'application_outcomes': outcomes,
        'recent_reviews': reviewed[:5], 'active_jobs': sum(is_published(j) for j in jobs_list),
        'pending_jobs': sum(j.get('review_status') not in ('Approved', 'Rejected') for j in jobs_list),
        'incomplete_profiles': sum(not u.get('profile_completed') for u in users_list),
        'refreshed_at': timezone.now(),
        'total_seekers': total_seekers,
        'total_employers': total_employers,
        'pending_clearances': pending_clearances,
        'total_jobs': total_jobs,
        'total_applications': total_applications,
    }
    return render(request, 'admin_panel/dashboard.html', context)

@role_required(allowed_roles=['admin'])
def verify_documents(request):
    """Retrieves job seekers awaiting clearance document audit (ID, NBI, Police, Barangay)."""
    users_ref = db.collection('users').stream()
    pending_users = []

    for user in users_ref:
        u_data = user.to_dict() | {'email': user.id}
        # Filter for candidates that have submitted documents or are awaiting verification
        if u_data.get('role') in ('job_seeker', 'employer') and u_data.get('clearance_status') in ['Pending', 'Under Review']:
            pending_users.append(u_data)

    return render(request, 'admin_panel/verify_documents.html', {'pending_users': pending_users})

@role_required(allowed_roles=['admin'])
def update_clearance_status(request, email):
    """Processes verification status updates: Verified, Rejected, or Correction Requested."""
    if request.method == "POST":
        new_status = request.POST.get('clearance_status')
        admin_notes = request.POST.get('admin_notes', '')
        from servinn_core.moderation import validate_respectful_text
        from django.core.exceptions import ValidationError
        try:
            validate_respectful_text(admin_notes)
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect('manage_users')
        if new_status not in ('Verified', 'Rejected', 'Correction Requested'):
            messages.error(request, 'Choose a valid review decision.')
            return redirect('manage_users')

        user_ref = db.collection('users').document(email)
        snapshot = user_ref.get()
        if snapshot.exists and snapshot.to_dict().get('role') in ('job_seeker', 'employer'):
            user_ref.update({
                'clearance_status': new_status,
                'verified': True if new_status == 'Verified' else False,
                'admin_notes': admin_notes,
                'reviewed_at': timezone.now(),
                'reviewed_by': request.user.get_username()
            })
            messages.success(request, f"Updated clearance status for {email} to '{new_status}'.")

    return redirect('manage_users')

@role_required(allowed_roles=['admin'])
def manage_users(request):
    """Admin oversight for viewing and managing all registered Job Seekers and Employers."""
    users_ref = db.collection('users').stream()
    all_users = [u.to_dict() | {'email': u.id} for u in users_ref]
    all_users = [u for u in all_users if u.get('role') in ('job_seeker', 'employer')]
    stats = {
        'total': len(all_users),
        'seekers': sum(u.get('role') == 'job_seeker' for u in all_users),
        'employers': sum(u.get('role') == 'employer' for u in all_users),
        'pending': sum(u.get('clearance_status', 'Pending') in ('Pending', 'Under Review') for u in all_users),
    }
    role = request.GET.get('role', '')
    query = request.GET.get('q', '').strip().lower()
    if role in ('job_seeker', 'employer'):
        all_users = [u for u in all_users if u.get('role') == role]
    if query:
        all_users = [u for u in all_users if query in ' '.join(str(u.get(key) or '') for key in ('email', 'full_name', 'company_name')).lower()]

    statuses = ['Pending', 'Under Review', 'Verified', 'Approved', 'Rejected', 'Correction Requested']
    status = request.GET.get('status', '')
    if status in statuses:
        all_users = [u for u in all_users if u.get('clearance_status', 'Pending') == status]
    sort = request.GET.get('sort', 'name')
    all_users.sort(key=lambda u: str(u.get('company_name') or u.get('full_name') or u['email']).lower(), reverse=sort == 'name_desc')
    page = Paginator(all_users, 10).get_page(request.GET.get('page'))
    filters = request.GET.copy()
    filters.pop('page', None)
    return render(request, 'admin_panel/manage_users.html', {
        'users': page, 'page_obj': page, 'stats': stats, 'statuses': statuses,
        'selected_status': status, 'selected_role': role, 'selected_sort': sort,
        'query': request.GET.get('q', ''), 'filter_query': filters.urlencode(),
    })

@role_required(allowed_roles=['admin'])
def system_reports(request):
    """Generates analytics reports on cross-matching performance and placement activity."""
    apps_ref = db.collection('applications').stream()
    apps_list = [a.to_dict() for a in apps_ref]

    total_apps = len(apps_list)
    shortlisted = sum(1 for a in apps_list if a.get('status') == 'Shortlisted')
    accepted = sum(1 for a in apps_list if a.get('status') == 'Accepted')
    rejected = sum(1 for a in apps_list if a.get('status') == 'Rejected')

    placement_rate = round((accepted / total_apps * 100), 2) if total_apps > 0 else 0.0

    context = {
        'total_apps': total_apps,
        'shortlisted': shortlisted,
        'accepted': accepted,
        'rejected': rejected,
        'placement_rate': placement_rate
    }
    return render(request, 'admin_panel/system_reports.html', context)


@role_required(allowed_roles=['admin'])
def manage_jobs(request):
    from jobs.publication import update_snapshot
    from employers.forms import EditJobForm
    if request.method == 'POST':
        job_id = request.POST.get('job_id', '')
        action = request.POST.get('action')
        note = request.POST.get('review_note', '').strip()[:2000]
        from servinn_core.moderation import validate_respectful_text
        from django.core.exceptions import ValidationError
        try:
            validate_respectful_text(note)
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect('admin_manage_jobs')
        if not job_id or '/' in job_id or action not in ('approve', 'reject', 'changes', 'close', 'archive'):
            messages.error(request, 'Choose a valid review action.')
            return redirect('admin_manage_jobs')
        ref = db.collection('job_postings').document(job_id)
        snapshot = ref.get()
        if not snapshot.exists:
            messages.error(request, 'Job posting not found.')
            return redirect('admin_manage_jobs')
        job = snapshot.to_dict()
        version = getattr(snapshot, 'update_time', None)
        from datetime import datetime
        if isinstance(version, datetime) and request.POST.get('version') != version.isoformat():
            messages.error(request, 'This job has changed. Review the latest content before making a decision.')
            return redirect('admin_manage_jobs')
        if action in ('reject', 'changes') and not note:
            messages.error(request, 'Explain your decision so the employer can correct the posting.')
            return redirect('admin_manage_jobs')
        if action == 'approve':
            content = dict(job)
            if isinstance(content.get('required_skills'), list):
                content['required_skills'] = ', '.join(content['required_skills'])
            if not EditJobForm(content).is_valid() or not job.get('employer_email'):
                messages.error(request, 'This job has incomplete or invalid details. Request corrections before approval.')
                return redirect('admin_manage_jobs')
        states = {'approve': ('Active', 'Approved'), 'reject': ('Rejected', 'Rejected'),
                  'changes': ('Changes Requested', 'Changes Requested')}
        changes = {'moderated_by': request.user.get_username(), 'moderated_at': timezone.now()}
        if action in states:
            status, review = states[action]
            changes.update(status=status, review_status=review, review_note=note,
                           reviewed_by=request.user.get_username(), reviewed_at=timezone.now(),
                           published_at=timezone.now() if action == 'approve' else None)
        else:
            changes['status'] = 'Closed' if action == 'close' else 'Archived'
        try:
            update_snapshot(db, ref, snapshot, changes)
        except Exception:
            messages.error(request, 'Unable to save this decision. Reload and review the job again.')
        else:
            messages.success(request, 'Review saved. Only approved, active jobs are published.')
        return redirect('admin_manage_jobs')
    jobs = []
    from datetime import datetime
    for doc in db.collection('job_postings').stream():
        job = doc.to_dict() | {'id': doc.id}
        version = getattr(doc, 'update_time', None)
        job['version'] = version.isoformat() if isinstance(version, datetime) else ''
        jobs.append(job)
    jobs.sort(key=lambda job: job.get('review_status') in ('Approved', 'Rejected'))
    query = request.GET.get('q', '').strip().casefold()
    if query:
        jobs = [job for job in jobs if query in str(job.get('title', '')).casefold() or query in str(job.get('company_name', '')).casefold()]
    return render(request, 'admin_panel/manage_jobs.html', {'jobs': Paginator(jobs, 20).get_page(request.GET.get('page')), 'query': query})
