from django.urls import path
from .views.automation_reports import automation_reports

urlpatterns = [
    path('', automation_reports, name='automation_reports'),
]
