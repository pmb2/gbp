from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.contrib.auth import login as auth_login, authenticate, logout
from allauth.socialaccount.models import SocialAccount, SocialLogin
from allauth.socialaccount.helpers import complete_social_login
from .models import Business, User, Notification
from .api.business_management import get_business_accounts, store_business_data


@login_required
def index(request):
    if not request.user.is_authenticated or not request.user.socialaccount_set.filter(provider='google').exists():
        # Clear session and state data
        request.session.flush()
        # Log the user out
        logout(request)
        # Redirect to login page
        return HttpResponseRedirect(reverse('login'))

    businesses = Business.objects.filter(user=request.user)
    users = User.objects.all()
    users_with_ids = [{'email': user.email, 'id': user.id} for user in users]
    unread_notifications_count = Notification.get_user_notifications(request.user.id).count()

    return render(request, 'index.html', {
        'dashboard_data': {'businesses': businesses, 'users': users_with_ids},
        'unread_notifications_count': unread_notifications_count
    })


def login(request):
    if request.user.is_authenticated:
        return redirect(reverse('index'))

    if request.method == 'POST':
        # Authenticate the user
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user is not None:
            auth_login(request, user)
            # Automatically redirect to Google OAuth login
            return redirect('/accounts/google/login/')
        else:
            # Return an error message if authentication fails
            return render(request, 'login.html', {'error': 'Invalid login credentials'})

    return render(request, 'login.html')


def register(request):
    return render(request, 'register.html')
