# accounts/adapter.py

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import login


class AccountAdapter(DefaultAccountAdapter):

    def confirm_email(self, request, email_address):
        response = super().confirm_email(request, email_address)

        # Force login after email confirmation so the user lands on dashboard
        if not request.user.is_authenticated:
            email_address.user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, email_address.user)

        return response


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Google (and other OAuth providers) already verify the user's email.
    This adapter marks those emails as verified so allauth's mandatory
    email verification gate doesn't block the login redirect.
    It also auto-connects the social account to any existing Prism account
    that shares the same email address.
    """

    def pre_social_login(self, request, sociallogin):
        from allauth.account.models import EmailAddress

        # Nothing to do if this social account is already linked to a user
        if sociallogin.is_existing:
            return

        email = (sociallogin.user.email or '').strip().lower()
        if not email:
            return

        # Mark the provider-supplied email as verified
        for email_obj in sociallogin.email_addresses:
            email_obj.verified = True

        # If a Prism account already exists with this email, connect to it
        try:
            existing_email = EmailAddress.objects.get(email__iexact=email)
            sociallogin.connect(request, existing_email.user)
        except EmailAddress.DoesNotExist:
            pass