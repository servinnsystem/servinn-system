from django.urls import path
from django.shortcuts import render, redirect
from accounts.privacy import privacy_policy

urlpatterns = [
    path('privacy-policy/', privacy_policy, name='privacy_policy'),
    # Main Landing Page (http://127.0.0.1:8000/)
    path('', lambda req: render(req, 'landing_page.html'), name='home'),

    # Dashboard Endpoints
    path('dashboard/jobseeker/', lambda req: redirect('jobseeker_dashboard'), name='legacy_jobseeker_dashboard'),
    path('dashboard/employer/', lambda req: redirect('employer_dashboard'), name='legacy_employer_dashboard'),
    path('dashboard/admin/', lambda req: redirect('admin_dashboard'), name='legacy_admin_dashboard'),
]
