from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # path('', include('gbp_django.urls')),  # Commented out to avoid recursion
]
