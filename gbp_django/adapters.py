from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialApp

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def get_app(self, request, provider, client_id=None):
        # Get the most recently created app if multiple exist
        provider_id = provider.id if hasattr(provider, 'id') else provider
        return SocialApp.objects.filter(provider=provider_id).latest('id')
        
    def get_callback_url(self, request, app):
        return 'https://gbp.backus.agency/google/callback/'
