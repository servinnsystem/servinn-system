"""
URL configuration for SERVINN_SYSTEM project.
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from django.templatetags.static import static as static_url
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url=static_url('images/servinn-logo.png.jpg'), permanent=False), name='favicon'),

    # ========================================================
    # DJANGO ADMIN
    # ========================================================

    path('admin/', admin.site.urls),


    # ========================================================
    # SERVINN APPLICATIONS
    # ========================================================

    # Main SERVINN landing page & general core routes
    path('', include('servinn_core.app_urls')),

    # Accounts - Login, Registration, Authentication
    path('accounts/', include('accounts.urls')),

    # Job Seeker Dashboard & Profile
    path('jobseeker/', include('jobseekers.urls')),

    # Employer Dashboard & Job Management
    path('employer/', include('employers.urls')),

    # Jobs Search and Matching Engine
    path('jobs/', include('jobs.urls')),

    # SERVINN System Administrator Portal
    path('portal-admin/', include('admin_panel.urls')),
]


# ============================================================
# STATIC AND MEDIA FILES (DEVELOPMENT ONLY)
# ============================================================

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.STATIC_ROOT
    )

    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )