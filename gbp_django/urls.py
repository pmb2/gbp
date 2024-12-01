from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import login_required
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', login_required(views.index), name='index'),
    path('accounts/', include('allauth.urls')),  # Ensure this line is present
    path('login/', views.login, name='login'),
    path('accounts/', include('allauth.urls')),  # Add this line
]
