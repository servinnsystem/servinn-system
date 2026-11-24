from django.urls import path
from . import views
from .signin_settings import signin_settings
from accounts.views import admin_login

urlpatterns = [
    path('sign-in-settings/', signin_settings, name='admin_signin_settings'),
    path('jobs/', views.manage_jobs, name='admin_manage_jobs'),
    path('login/', admin_login, name='portal_admin_login'),
    # Maps /portal-admin/ directly to the dashboard view
    path('', views.dashboard, name='portal_admin'),
    path('dashboard/', views.dashboard, name='admin_dashboard'),
    path('verify-docs/', views.verify_documents, name='verify_documents'),
    path('verify-docs/<str:email>/action/', views.update_clearance_status, name='update_clearance_status'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('accounts/<str:account_id>/', views.account_profile, name='admin_account_profile'),
    path('reports/', views.system_reports, name='system_reports'),
]   
