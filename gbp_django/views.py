from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import login as auth_login
from allauth.socialaccount.models import SocialAccount
from .models import Business, User, Notification
from .api.business_management import get_business_accounts, store_business_data


def index(request):
    if not request.user.is_authenticated or not request.user.socialaccount_set.filter(provider='google').exists():
        return redirect(reverse('google_login'))
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
        social_account = SocialAccount.objects.get(user=request.user, provider='google')
        access_token = social_account.socialtoken_set.first().token

        # Fetch and store business accounts
        business_data = get_business_accounts(access_token)
        store_business_data(business_data, request.user.id)

        # Redirect to index after successful login and data collection
        return redirect(reverse('index'))

    return render(request, 'login.html')
