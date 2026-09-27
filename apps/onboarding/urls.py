"""
URL configuration for onboarding multi-step wizard.
"""
from django.urls import path
from . import views

app_name = 'onboarding'

urlpatterns = [
    path('', views.step_1_view, name='index'),
    path('step-1/', views.step_1_view, name='step_1'),
    path('api/save-draft/', views.save_step1_draft_view, name='save_step1_draft'),
    path('step-2-certificate/', views.step_2_certificate_view, name='step_2_certificate'),
    path('api/parse-certificate/', views.parse_certificate_api_view, name='parse_certificate'),
    path('diagnostic/', views.diagnostic_view, name='diagnostic'),
    path('diagnostic/submit/', views.diagnostic_view, name='diagnostic_submit'),
    path('step-3-matching/', views.step_3_matching_view, name='step_3_matching'),
    path('step-4-timeline/', views.step_4_timeline_view, name='step_4_timeline'),
    path('results/', views.results_view, name='results'),
]
