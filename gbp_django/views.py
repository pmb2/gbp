from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.contrib.auth import login as auth_login
from allauth.socialaccount.models import SocialAccount, SocialLogin
from allauth.socialaccount.helpers import complete_social_login
from .models import Business, User, Notification
from .api.business_management import get_business_accounts, store_business_data


@login_required
def index(request):

    if not request.user.socialaccount_set.filter(provider='google').exists():
        return redirect('account_login')  # Redirect to Google login if not linked

    if not isinstance(request.user, User):
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
        # Handle OAuth callback
        social_login = SocialLogin.objects.get(user=request.user, provider='google')
        if not social_login.is_existing:
            # Link the social account to the existing user
            social_login.user = request.user
            complete_social_login(request, social_login)

        access_token = social_login.token.token

        # Fetch and store business accounts
        business_data = get_business_accounts(access_token)
        store_business_data(business_data, request.user.id)

        # Redirect to index after successful login and data collection
        return redirect(reverse('index'))

    return render(request, 'login.html')

def register(request):
    return render(request, 'register.html')
