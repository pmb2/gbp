from django.shortcuts import render
from .models import Business, User

def index(request):
    businesses = Business.objects.all()
    users = User.objects.all()
    users_with_ids = [{'email': user.email, 'id': user.id} for user in users]
    return render(request, 'index.html', {'dashboard_data': {'businesses': businesses, 'users': users_with_ids}})

def login(request):
    return render(request, 'login.html')
