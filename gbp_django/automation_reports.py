from django.shortcuts import render

def automation_reports(request):
    context = {
        'reports': [],
        'dashboard_url': '/dashboard/',
    }
    return render(request, 'automation_reports.html', context)
