from django.shortcuts import render
from .models import Business, User

def index(request):
    print("Fetching all businesses and users for the dashboard.")
    businesses = Business.objects.all()
    print(f"Businesses fetched: {businesses}")
    users = User.objects.all()
    print(f"Users fetched: {users}")
    users_with_ids = [{'email': user.email, 'id': user.id} for user in users]
    print(f"Users with IDs prepared: {users_with_ids}")
    print("Rendering index page with dashboard data.")
    return render(request, 'index.html', {'dashboard_data': {'businesses': businesses, 'users': users_with_ids}})

def login(request):
    print("Rendering login page.")
    return render(request, 'login.html')
