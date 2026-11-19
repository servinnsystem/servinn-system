# employers/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('jobs/<str:job_id>/status/', views.job_status, name='job_status'),
    path('dashboard/', views.dashboard, name='employer_dashboard'),
    path('setup-company/', views.create_company, name='create_company'),
    path('post-job/', views.post_job, name='post_job'),
    path('jobs/<str:job_id>/edit/', views.edit_job, name='edit_job'),
    path('applicants/', views.view_applicants, name='view_applicants'),
    path('applicants/<str:app_id>/update-status/', views.update_applicant_status, name='update_applicant_status'),
    
    # Added search route for location-based & keyword search
    path('search/', views.search_jobs, name='search_jobs'),
]
