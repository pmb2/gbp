from django.shortcuts import render, redirect
from django.urls import reverse
from .models import Business, User, Notification

def index(request):
    if not request.user.is_authenticated or not request.user.socialaccount_set.filter(provider='google').exists():
        return redirect(reverse('socialaccount:socialaccount_login', kwargs={'provider': 'google'}))
    businesses = Business.objects.all()
    print(f"Businesses fetched: {businesses}")
    users = User.objects.all()
    print(f"Users fetched: {users}")
    users_with_ids = [{'email': user.email, 'id': user.id} for user in users]
    print(f"Users with IDs prepared: {users_with_ids}")
    unread_notifications_count = Notification.get_user_notifications(request.user.id).count()
    print(f"Unread notifications count: {unread_notifications_count}")
    print("Rendering index page with dashboard data.")
    return render(request, 'index.html', {
        'dashboard_data': {'businesses': businesses, 'users': users_with_ids},
        'unread_notifications_count': unread_notifications_count
    })

def login(request):
    print("Rendering login page.")
    return render(request, 'login.html')
