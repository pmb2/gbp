from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialApp

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def get_app(self, request, provider, client_id=None):
        # Get the most recently created app if multiple exist
        return SocialApp.objects.filter(provider=provider.id).latest('id')
