"""
URL configuration for study abroad platform MVP.
"""
from django.contrib import admin
from django.urls import path, include
from apps.core.views import landing_page_view

from apps.dashboard.views import calendar_view, stats_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('onboarding/', include('apps.onboarding.urls', namespace='onboarding')),
    path('tasks/', include('apps.tasks.urls', namespace='tasks')),
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('documents/', include('apps.documents.urls', namespace='documents')),
    path('resources/', include('apps.resources.urls', namespace='resources')),
    path('calendar/', calendar_view, name='calendar_direct'),
    path('stats/', stats_view, name='stats_direct'),
    path('mentor/', include('apps.mentor.urls', namespace='mentor')),
    path('programs/', include('apps.programs.urls', namespace='programs')),
    path('mock-exams/', include('apps.mock_exams.urls', namespace='mock_exams')),
    path('', landing_page_view, name='home'),
]

from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path
from django.views.static import serve

urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
