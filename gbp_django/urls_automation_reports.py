from django.urls import path
from gbp_django.automation_reports import automation_reports

urlpatterns = [
    path('', automation_reports, name='automation_reports'),
]
