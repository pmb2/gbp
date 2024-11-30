from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('gbp_django.urls')),  # Ensure this path is correct for Django app structure
]
