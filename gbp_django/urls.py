from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.decorators import login_required
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.root_view, name='root'),
    path('dashboard/', login_required(views.index), name='index'),
    path('accounts/', include('allauth.urls')),
    path('login/', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('google/callback/', views.google_oauth_callback, name='google_oauth_callback'),
    path('google/auth/', views.direct_google_oauth, name='google_oauth'),
    path('api/business/<str:business_id>/verification-status/', 
         views.get_verification_status, name='verification_status'),
    path('api/notifications/', views.get_notifications, name='get_notifications'),
    path('api/notifications/<int:notification_id>/dismiss/', 
         views.dismiss_notification, name='dismiss_notification'),
]
