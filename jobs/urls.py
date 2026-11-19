# jobs/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('<str:job_id>/employer/', views.employer_profile, name='job_employer_profile'),
    path('<str:job_id>/employer/photo/', views.employer_photo, name='job_employer_photo'),
    path('search/', views.job_search, name='job_search'),
    path('recommendations/', views.job_recommendations, name='job_recommendations'),
    path('<str:job_id>/', views.job_detail, name='job_detail'),
]
