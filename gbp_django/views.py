from django.shortcuts import render
from .models import Business, User

def index(request):
    businesses = Business.objects.all()
    users = User.objects.all()
    return render(request, 'index.html', {'dashboard_data': {'businesses': businesses, 'users': users}})

def login(request):
    return render(request, 'login.html')
