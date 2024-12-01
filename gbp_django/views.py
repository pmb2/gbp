from django.shortcuts import render
from .models import Business

def index(request):
    businesses = Business.objects.all()
    return render(request, 'index.html', {'dashboard_data': {'businesses': businesses}})

def login(request):
    return render(request, 'login.html')
