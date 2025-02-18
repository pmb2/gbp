# [REG FLOW] Custom Account Adapter for troubleshooting registration flow.
from allauth.account.adapter import DefaultAccountAdapter

class CustomAccountAdapter(DefaultAccountAdapter):
    def get_current_site(self, request):
        site = super().get_current_site(request)
        print("[REG FLOW] get_current_site called. Request host:", request.get_host(), "Site:", site)
        return site

    def save_user(self, request, user, form, commit=True):
        print("[REG FLOW] save_user called for user:", user.email)
        return super().save_user(request, user, form, commit)
