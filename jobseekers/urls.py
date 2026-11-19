from django.urls import path
from . import views

urlpatterns = [
    path('jobs/<str:job_id>/rate/', views.rate_job, name='rate_job'),
    path('application-updates/', views.application_updates, name='application_updates'),
    path('save/<str:job_id>/', views.toggle_save_job, name='toggle_save_job'),
    # Dashboard routes
    path('dashboard/', views.dashboard, name='jobseeker_dashboard'),
    path('dashboard/alt/', views.dashboard, name='dashboard'),
    
    # Navigation routes
    path('my-applications/', views.my_applications, name='my_applications'),
    path('saved-jobs/', views.saved_jobs, name='saved_jobs'),
    path('notifications/', views.dashboard, name='notifications'),
    path('about-us/', views.about_us, name='about_us'),
    
    # Application & Job management
    path('apply/<str:job_id>/', views.apply_job, name='apply_job'),
    path('application-tracker/', views.application_tracker, name='application_tracker'),
    path('delete-application/<str:application_id>/', views.delete_application, name='delete_application'),
    path('jobs/', views.jobs_list, name='jobs_list'),
    
    # Profile management
    path('create-profile/', views.create_profile, name='jobseeker_create_profile'),
    path('profile-setup/', views.profile_setup, name='profile_setup'),
    path('upload-documents/', views.upload_documents, name='upload_documents'),
]
