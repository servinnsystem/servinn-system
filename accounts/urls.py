# accounts/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('verify-google-email/', views.verify_google_email, name='verify_google_email'),
    path('phone-login/', views.phone_login, name='phone_login'),
    path('profile-file/<str:email>/<str:kind>/', views.profile_file, name='profile_file'),
    # Authentication & Root Routes
    path('', views.login_view, name='accounts_home'),
    path('login/', views.login_view, name='login'),
    path('login/admin/', views.admin_login, name='admin_login'),
    path('google-login/', views.google_login, name='google_login'),
    path('google-callback/', views.google_callback, name='google_callback'),
    path('logout/', views.logout_view, name='logout'),
    
    # Registration Endpoints
    path('register/', views.register_seeker, name='register'),
    path('register/seeker/', views.register_seeker, name='register_seeker'),
    path('register/employer/', views.register_employer, name='register_employer'),
    
    # Profile Setup & Verification
    path('create-profile/', views.create_profile, name='create_profile'),
    
    # Dashboards & Landing
    path('landing/', views.landing_page, name='landing_page'),
    path('jobseeker/dashboard/', views.jobseeker_dashboard, name='legacy_account_jobseeker_dashboard'),
]
