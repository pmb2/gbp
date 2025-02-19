from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.decorators import login_required
from . import views
from gbp_django.api import automation
from django.conf import settings
from django.conf.urls.static import static
from allauth.account.views import LoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', views.root_view, name='root'),
    path('dashboard/', login_required(views.index), name='index'),
    path('login/', views.login, name='login'),
    path('google/callback/', views.google_oauth_callback, name='google_oauth_callback'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('google/auth/', views.direct_google_oauth, name='direct_google_oauth'),
    path('api/business/<str:business_id>/verification-status/', 
         views.get_verification_status, name='verification_status'),
    path('api/notifications/', views.get_notifications, name='get_notifications'),
    path('api/notifications/<int:notification_id>/dismiss/', 
         views.dismiss_notification, name='dismiss_notification'),
    path('api/notifications/mark-all-read/',
         views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('api/business/<str:business_id>/knowledge/', views.add_knowledge, name='add_knowledge'),
    path('api/business/<str:business_id>/update/',
         views.update_business, name='update_business'),
    path('api/business/<str:business_id>/automation/',
         views.update_automation_settings, name='update_automation'),
    path('api/business/bulk-upload/',
         views.bulk_upload_businesses, name='bulk_upload_businesses'),
    path('api/business/verify-email/<str:token>/',
         views.verify_business_email, name='verify_business_email'),
    path('api/feedback/',
         views.submit_feedback, name='submit_feedback'),
    path('api/business/<str:business_id>/chat/',
         views.chat_message, name='chat_message'),
    path('api/business/<str:business_id>/files/<int:file_id>/preview/',
         views.preview_file, name='preview_file'),
    path('api/business/<str:business_id>/files/<int:file_id>/preview/',
         views.preview_file, name='preview_file'),
    path('api/business/<str:business_id>/memories/',
         views.get_memories, name='get_memories'),
    path('submit-feedback/', views.submit_feedback, name='submit_feedback'),
    path('api/business/<str:business_id>/tasks/create/', views.create_task, name='create_task'),
    path('api/business/<str:business_id>/tasks/update/', views.create_task, name='update_task'),
    path('api/generate-content/', views.generate_content, name='generate_content'),
    path('api/business/<str:business_id>/seo-health/', views.get_seo_health, name='get_seo_health'),
    path('api/automation/fallback/<str:business_id>/', automation.automation_fallback, name='automation_fallback'),
]

# Serve static files
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
