import json
import base64
from django.shortcuts import render, redirect  # type: ignore
from django.contrib import messages  # type: ignore
from django.http import JsonResponse  # type: ignore
from django.utils import timezone
from django.views.decorators.cache import never_cache
from servinn_core.firebase_config import db  # type: ignore
from django.contrib.auth import authenticate, login
from django.contrib.auth.hashers import make_password
from google.api_core.exceptions import AlreadyExists
from .passwords import verify_account_password

def landing_page(request):
    """Renders the main landing page."""
    return redirect('home')

def login_view(request):
    """Renders the Login page and routes user based on profile completion status."""
    if request.method == "POST":
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        if not email or not password:
            messages.error(request, "Please fill in all fields.")
            return render(request, 'accounts/login.html')

        user_ref = db.collection('users').document(email)
        snapshot = user_ref.get()
        if snapshot.exists:
            user_data = snapshot.to_dict()

            if user_data.get('role') == 'admin':
                return redirect('admin_login')

            # Validate password
            password_valid, needs_hashing = verify_account_password(password, user_data.get('password'))
            if password_valid and user_data.get('role') in ('job_seeker', 'employer'):
                if needs_hashing:
                    try:
                        user_ref.update({'password': make_password(password)})
                    except Exception:
                        messages.error(request, 'Unable to complete sign-in. Please try again.')
                        return render(request, 'accounts/login.html', status=503)
                request.session.cycle_key()
                # Save User Session
                request.session['user_email'] = email
                request.session['user_role'] = user_data.get('role')
                request.session['user_name'] = user_data.get('full_name') or user_data.get('company_name')

                # Check profile completion status
                profile_completed = user_data.get('profile_completed', False)

                # Route to Create Profile if not completed yet
                if not profile_completed and user_data.get('role') != 'admin':
                    return redirect('create_profile')

                # Route to respective dashboard if profile is completed
                if user_data.get('role') == 'employer':
                    return redirect('employer_dashboard')
                elif user_data.get('role') == 'admin':
                    return redirect('admin_dashboard')
                else:
                    return redirect('jobseeker_dashboard')

        messages.error(request, "Invalid email or password.")
        return render(request, 'accounts/login.html')

    return render(request, 'accounts/login.html')

def register_view(request):
    """Renders the account registration page."""
    return render(request, 'accounts/register.html')

def register_seeker(request):
    """Processes Job Seeker registration POST requests and redirects to Login page."""
    if request.method == "POST":
        first_name = request.POST.get('first_name', '').strip()
        middle_name = request.POST.get('middle_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        skills = [s.strip() for s in request.POST.get('skills', '').split(',') if s.strip()]

        # Construct full name dynamically
        name_parts = [p for p in [first_name, middle_name, last_name] if p]
        full_name = " ".join(name_parts)

        from servinn_core.moderation import validate_respectful_text
        from django.core.exceptions import ValidationError
        try:
            validate_respectful_text(first_name)
            validate_respectful_text(middle_name)
            validate_respectful_text(last_name)
            validate_respectful_text(skills)
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return render(request, 'accounts/register.html')

        if not email or not password:
            messages.error(request, "Email and password are required.")
            return render(request, 'accounts/register.html')

        try:
            # Store initial Job Seeker Data in Firestore
            seeker_data = {
                'first_name': first_name,
                'middle_name': middle_name,
                'last_name': last_name,
                'full_name': full_name,
                'email': email,
                'password': make_password(password),
                'skills': skills,
                'role': 'job_seeker',
                'verified': False,
                'profile_completed': False,
                'clearance_status': 'Pending'
            }
            db.collection('users').document(email).create(seeker_data)

            # Prompt user to log in before creating profile
            messages.success(request, "Registration successful! Please log in to complete your profile.")
            return redirect('login')

        except AlreadyExists:
            messages.error(request, 'An account with this email already exists. Please sign in.')
            return render(request, 'accounts/register.html')
        except Exception:
            messages.error(request, 'Registration failed. Please try again.')
            return render(request, 'accounts/register.html')

    # Fix for ERR_TOO_MANY_REDIRECTS: render template directly on GET request
    return render(request, 'accounts/register.html')

def register_employer(request):
    """Processes Employer registration POST requests and redirects to Login page."""
    if request.method == "POST":
        company_name = request.POST.get('company_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        location = request.POST.get('location', '').strip()

        from servinn_core.moderation import validate_respectful_text
        from django.core.exceptions import ValidationError
        try:
            validate_respectful_text(company_name)
            validate_respectful_text(location)
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return render(request, 'accounts/register.html')

        if not email or not password:
            messages.error(request, "Email and password are required.")
            return render(request, 'accounts/register.html')

        try:
            employer_data = {
                'company_name': company_name,
                'email': email,
                'password': make_password(password),
                'location': location,
                'role': 'employer',
                'verified': True,
                'profile_completed': False
            }
            db.collection('users').document(email).create(employer_data)

            messages.success(request, f"Employer account created for {company_name}. Please log in to continue.")
            return redirect('login')

        except AlreadyExists:
            messages.error(request, 'An account with this email already exists. Please sign in.')
            return render(request, 'accounts/register.html')
        except Exception:
            messages.error(request, 'Employer registration failed. Please try again.')
            return render(request, 'accounts/register.html')

    # Fix for ERR_TOO_MANY_REDIRECTS: render template directly on GET request
    return render(request, 'accounts/register.html')

@never_cache
def create_profile(request):
    """Handles profile verification form submission and uploads files to Firestore."""
    from jobs.categories import skill_category_choices, category_from_skills, normalize_skills
    user_email = request.session.get('user_email')

    if not user_email:
        return redirect('login')
    user_ref = db.collection('users').document(user_email)
    snapshot = user_ref.get()
    if not snapshot.exists:
        return redirect('login')
    user_data = snapshot.to_dict()
    def profile_context(values):
        selected = normalize_skills(values.getlist('skills') if hasattr(values, 'getlist') else values.get('skills'))
        return {'user_data': values, 'selected_skills': selected,
                'job_categories': skill_category_choices(selected)}
    if user_data.get('profile_completed'):
        return redirect('employer_dashboard' if user_data.get('role') == 'employer' else 'jobseeker_dashboard')

    if request.method == 'POST':
        selected_role = request.POST.get('role', request.session.get('user_role', 'job_seeker'))
        
        first_name = request.POST.get('first_name', '').strip()
        middle_name = request.POST.get('middle_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        company_name = request.POST.get('company_name', '').strip()
        email = user_data.get('email', '') if user_data.get('auth_provider') == 'phone' else user_email
        contact_number = request.POST.get('contact_number', '').strip()
        gender = request.POST.get('gender', '').strip()
        id_type = request.POST.get('id_type', '').strip()
        skills = [s.strip() for s in request.POST.get('skills', '').split(',') if s.strip()]

        name_parts = [p for p in [first_name, middle_name, last_name] if p]
        full_name = " ".join(name_parts) or company_name

        from .profile_forms import VerificationForm
        verification = VerificationForm(request.POST, request.FILES, initial=user_data)
        if not verification.is_valid():
            for field, errors in verification.errors.items():
                for error in errors:
                    messages.error(request, f"{verification.fields[field].label or field.replace('_', ' ').title()}: {error}")
            return render(request, 'accounts/create_profile.html', profile_context(request.POST))
        contact_number = verification.cleaned_data['contact_number']
        skills = verification.cleaned_data['skills']

        profile_photo = request.FILES.get('profile_photo')
        id_file = request.FILES.get('id_file')
        id_back_file = request.FILES.get('id_back_file')
        selfie_file = request.FILES.get('selfie_file')
        resume_file = request.FILES.get('resume_file')

        update_payload = {
            'role': selected_role,
            'first_name': first_name,
            'middle_name': middle_name,
            'last_name': last_name,
            'company_name': company_name,
            'full_name': full_name or request.session.get('user_name', ''),
            'email': email,
            'contact_number': contact_number,
            'gender': gender,
            'date_of_birth': verification.cleaned_data['date_of_birth'].isoformat() if verification.cleaned_data.get('date_of_birth') else '',
            'nationality': verification.cleaned_data['nationality'],
            'id_type': id_type,
            'id_number': verification.cleaned_data['id_number'],
            'complete_address': verification.cleaned_data['complete_address'],
            'street_address': verification.cleaned_data['street_address'],
            'barangay': verification.cleaned_data['barangay'],
            'city_municipality': verification.cleaned_data['city_municipality'],
            'province': verification.cleaned_data['province'],
            'postal_code': verification.cleaned_data['postal_code'],
            'skills': skills,
            'category_preference': category_from_skills(skills) if selected_role == 'job_seeker' else '',
            'profile_completed': True,
            'clearance_status': 'Under Review',
            'verified': False,
            'declaration_accepted': True,
            'user_agreement_accepted': True,
            'user_agreement_version': '2026-11-14.2',
            'user_agreement_accepted_at': timezone.now(),
        }

        from .uploads import private_storage, save_upload
        saved_paths = []
        try:
            for field, upload in [('profile_photo', profile_photo), ('id_document', id_file),
                                  ('id_document_back', id_back_file), ('selfie_document', selfie_file),
                                  ('resume_document', resume_file)]:
                if upload:
                    metadata = save_upload(upload)
                    saved_paths.append(metadata['path'])
                    update_payload[field + '_file'] = metadata
            target_email = user_email
            if target_email:
                db.collection('users').document(target_email).update(update_payload)
                request.session['user_email'] = target_email
                request.session['user_role'] = selected_role
                request.session['user_name'] = company_name if selected_role == 'employer' else update_payload['full_name']
            
            messages.success(request, "Profile submitted for administrator review.")
            
            # Route directly to respective dashboard after profile creation
            if selected_role == 'employer':
                return redirect('employer_dashboard')
            return redirect('jobseeker_dashboard')
            
        except Exception as e:
            for path in saved_paths:
                private_storage.delete(path)
            messages.error(request, 'Unable to save your profile. Please try again and reselect your files.')
            return render(request, 'accounts/create_profile.html', profile_context(request.POST))

    return render(request, 'accounts/create_profile.html', profile_context(user_data))

def jobseeker_dashboard(request):
    """Preserve old bookmarks through the protected dashboard route."""
    return redirect('jobseeker_dashboard')

def google_login(request):
    return social_login(request, expected_provider='google.com')


def social_login(request, expected_provider):
    """Create a Django session only after Firebase verifies the provider token."""
    from firebase_admin import auth
    from django.urls import reverse

    if request.method != 'POST':
        return JsonResponse({'message': 'POST required.'}, status=405)
    try:
        data = json.loads(request.body)
        token = data.get('id_token') if isinstance(data, dict) else None
        if not isinstance(token, str) or not token:
            raise ValueError('Missing token')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'message': 'A Firebase sign-in token is required.'}, status=400)
    try:
        claims = auth.verify_id_token(token, check_revoked=True)
    except Exception:
        return JsonResponse({'message': 'Unable to verify sign-in. Please try again.'}, status=401)
    if claims.get('firebase', {}).get('sign_in_provider') != expected_provider:
        return JsonResponse({'message': 'The sign-in provider does not match.'}, status=401)
    email = (claims.get('email') or '').strip().lower()
    uid = claims.get('uid') or claims.get('sub')
    if not email or not uid:
        return JsonResponse({'message': 'Your Google account must share an email address to continue.'}, status=400)
    try:
        user_ref = db.collection('users').document(email)
        snapshot = user_ref.get()
        if snapshot.exists:
            user_data = snapshot.to_dict()
            # Existing email accounts require a verified address or an already bound UID.
            if user_data.get('firebase_uid'):
                if user_data['firebase_uid'] != uid:
                    return JsonResponse({'message': 'This email is linked to another sign-in account.'}, status=403)
            elif not claims.get('email_verified'):
                return JsonResponse({'message': 'Verify your provider email before signing into this existing account.'}, status=403)
            if user_data.get('role') not in ('job_seeker', 'employer'):
                return JsonResponse({'message': 'Use the administrator login for this account.'}, status=403)
        else:
            role = request.GET.get('role', 'job_seeker')
            if role not in ('job_seeker', 'employer'):
                return JsonResponse({'message': 'Invalid account type.'}, status=400)
            user_data = {
                'email': email, 'full_name': claims.get('name') or email.split('@')[0],
                'first_name': (claims.get('name') or '').split(' ', 1)[0],
                'last_name': (claims.get('name') or '').split(' ', 1)[1] if ' ' in (claims.get('name') or '') else '',
                'firebase_uid': uid, 'role': role, 'auth_provider': expected_provider,
                'verified': False, 'profile_completed': False, 'clearance_status': 'Pending',
                'created_at': timezone.now(),
            }
    except Exception:
        return JsonResponse({'message': 'Unable to load your account. Please try again.'}, status=503)

    from .email_auth import issue, EmailAuthError
    try:
        challenge = issue({'email': email, 'uid': uid, 'user_data': user_data,
                           'email_verified': bool(claims.get('email_verified'))})
    except EmailAuthError as error:
        return JsonResponse({'message': str(error)}, status=error.status)
    old_challenge = request.session.get('google_email_challenge')
    if old_challenge:
        from django.core.cache import cache
        cache.delete('email-auth:challenge:' + old_challenge)
    request.session.flush()
    request.session['google_email_challenge'] = challenge
    return JsonResponse({'status': 'verification_required', 'redirect_url': reverse('verify_google_email')})


def verify_google_email(request):
    from .email_auth import pending_for, consume, resend, EmailAuthError
    from django.urls import reverse
    token = request.session.get('google_email_challenge')
    try:
        pending = pending_for(token)
    except EmailAuthError:
        messages.error(request, 'Please start Google sign-in again to receive a new code.')
        return redirect('login')
    error = None
    response_status = 200
    if request.method == 'POST':
        try:
            if request.POST.get('action') == 'resend':
                resend(token)
                messages.success(request, 'A new code has been sent. Check your inbox and spam folder.')
                return redirect('verify_google_email')
            verified = consume(token, request.POST.get('code', '').strip())
            # Recheck account ownership at completion, after the email code succeeds.
            user_ref = db.collection('users').document(verified['email'])
            snapshot = user_ref.get()
            if snapshot.exists:
                user_data = snapshot.to_dict()
                if (user_data.get('role') not in ('job_seeker', 'employer')
                        or (user_data.get('firebase_uid') and user_data['firebase_uid'] != verified['uid'])):
                    raise EmailAuthError('This account cannot be used for this Google sign-in.', 403)
                user_ref.update({'firebase_uid': verified['uid'], 'email_verified': True})
            else:
                user_data = verified['user_data']
                user_data['email_verified'] = True
                user_ref.create(user_data)
            request.session.flush()
            request.session['user_email'] = verified['email']
            request.session['user_role'] = user_data['role']
            request.session['user_name'] = user_data.get('full_name') or user_data.get('company_name', '')
            if not user_data.get('profile_completed'):
                return redirect('create_profile')
            return redirect('employer_dashboard' if user_data['role'] == 'employer' else 'jobseeker_dashboard')
        except EmailAuthError as exc:
            error, response_status = str(exc), exc.status
        except Exception:
            error, response_status = 'Unable to finish sign-in. Please start Google sign-in again.', 503
    response = render(request, 'accounts/verify_google_email.html', {
        'verification_email': pending['email'], 'verification_error': error}, status=response_status)
    response['Cache-Control'] = 'private, no-store'
    return response


def admin_login(request):
    if request.user.is_authenticated and request.user.is_active and request.user.is_superuser:
        return redirect('admin_dashboard')
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username', ''),
                            password=request.POST.get('password', ''))
        if user is not None and user.is_active and user.is_superuser:
            request.session.flush()
            login(request, user)
            request.session['user_role'] = 'admin'
            request.session['user_email'] = user.email or user.username
            request.session['user_name'] = user.get_full_name() or user.username
            return redirect('admin_dashboard')
        messages.error(request, 'Invalid administrator credentials.')
    return render(request, 'admin_panel/login.html')


def logout_view(request):
    """Flushes user session data."""
    request.session.flush()
    messages.info(request, "You have been logged out.")
    return redirect('login')

def home_view(request):
    """Routes active sessions to their respective role dashboard."""
    role = request.session.get('user_role')
    
    if role == 'admin':
        return redirect('admin_dashboard')
    elif role == 'employer':
        return redirect('employer_dashboard')
    elif role == 'job_seeker':
        return redirect('jobseeker_dashboard')
    else:
        return redirect('login')

def profile_file(request, email, kind):
    from django.http import FileResponse, HttpResponseForbidden, Http404
    from .uploads import private_storage
    if not request.session.get('user_email'):
        return HttpResponseForbidden()
    if kind not in ('profile_photo', 'id_document', 'id_document_back', 'selfie_document', 'resume_document', 'nbi_clearance', 'police_clearance', 'barangay_clearance'):
        raise Http404
    if request.session.get('user_email') != email and not (request.user.is_authenticated and request.user.is_active and request.user.is_superuser):
        return HttpResponseForbidden()
    snapshot = db.collection('users').document(email).get()
    metadata = (snapshot.to_dict() or {}).get(kind + '_file') if snapshot.exists else None
    if not metadata:
        raise Http404
    try:
        response = FileResponse(private_storage.open(metadata['path'], 'rb'),
                                as_attachment=kind != 'profile_photo',
                                filename=metadata['name'], content_type=metadata['content_type'])
    except FileNotFoundError:
        raise Http404
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def phone_login(request):
    import re
    from firebase_admin import auth
    from django.urls import reverse
    if request.method != 'POST':
        return JsonResponse({'message': 'POST required.'}, status=405)
    try:
        data = json.loads(request.body)
        token = data.get('id_token') if isinstance(data, dict) else None
        if not isinstance(token, str) or not token:
            raise ValueError()
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'message': 'A verified phone sign-in token is required.'}, status=400)
    try:
        claims = auth.verify_id_token(token, check_revoked=True)
    except Exception:
        return JsonResponse({'message': 'Phone verification failed. Please sign in again.'}, status=401)
    phone = claims.get('phone_number', '')
    uid = claims.get('uid') or claims.get('sub')
    if claims.get('firebase', {}).get('sign_in_provider') != 'phone' or not uid or not re.fullmatch(r'\+639\d{9}', phone):
        return JsonResponse({'message': 'Verify a Philippine mobile number to continue.'}, status=401)
    # Stable account key; never link an account using an unverified contact field.
    key = 'phone:' + phone
    try:
        ref = db.collection('users').document(key)
        snapshot = ref.get()
        if snapshot.exists:
            user = snapshot.to_dict()
            if user.get('firebase_uid') != uid or user.get('role') not in ('job_seeker', 'employer'):
                return JsonResponse({'message': 'This phone identity cannot access this account.'}, status=403)
        else:
            role = request.GET.get('role', 'job_seeker')
            if role not in ('job_seeker', 'employer'):
                return JsonResponse({'message': 'Invalid account type.'}, status=400)
            user = {'email': '', 'phone_number': phone, 'contact_number': phone,
                    'phone_verified': True, 'firebase_uid': uid, 'role': role,
                    'auth_provider': 'phone', 'full_name': '', 'verified': False,
                    'profile_completed': False, 'clearance_status': 'Pending'}
            ref.create(user)
    except Exception:
        return JsonResponse({'message': 'Unable to load your account. Please try again.'}, status=503)
    request.session.flush()
    request.session['user_email'] = key
    request.session['user_role'] = user['role']
    request.session['user_name'] = user.get('full_name') or user.get('company_name', '')
    request.session['login_phone'] = phone
    destination = 'create_profile' if not user.get('profile_completed') else ('employer_dashboard' if user['role'] == 'employer' else 'jobseeker_dashboard')
    return JsonResponse({'redirect_url': reverse(destination)})
