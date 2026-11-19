# accounts/decorators.py
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def role_required(allowed_roles=None):
    """
    Decorator to restrict access to views based on user session role stored from Firebase.
    allowed_roles: List of allowed user roles, e.g., ['job_seeker', 'employer', 'admin']
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if 'admin' in (allowed_roles or ()):
                user = getattr(request, 'user', None)
                if not user or not user.is_authenticated or not user.is_active or not user.is_superuser:
                    return redirect('admin_login')
                return view_func(request, *args, **kwargs)

            user_role = request.session.get('user_role')
            user_email = request.session.get('user_email')

            # Check if user is logged in
            if not user_email or not user_role:
                messages.error(request, "Please log in to access this page.")
                return redirect('login')

            # Check if user role matches allowed roles
            if user_role not in (allowed_roles or ()):
                dashboards = {
                    'employer': 'employer_dashboard',
                    'job_seeker': 'jobseeker_dashboard',
                    'admin': 'admin_dashboard',
                }
                destination = dashboards.get(user_role)
                if not destination:
                    request.session.flush()
                    messages.error(request, 'Please log in again to continue.')
                    return redirect('login')
                role_label = user_role.replace('_', ' ')
                messages.info(request, (
                    f'You are signed in as a {role_label}. This page is for a different account type. '
                    'You have been returned to your dashboard. Sign out to switch accounts.'
                ))
                return redirect(destination)

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator