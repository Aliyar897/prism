import re
from django import forms
from django.contrib.auth.models import User
from allauth.account.forms import SignupForm


class CustomSignupForm(SignupForm):
    """
    Extends allauth SignupForm to enforce lowercase-alphanumeric usernames.
    The username field itself is added by allauth via ACCOUNT_SIGNUP_FIELDS.
    """

    def clean_username(self):
        val = self.cleaned_data.get('username', '').strip().lower()
        if not re.match(r'^[a-z0-9_]{3,30}$', val):
            raise forms.ValidationError(
                'Use 3–30 characters: letters (a–z), numbers, or underscores only.'
            )
        if User.objects.filter(username__iexact=val).exists():
            raise forms.ValidationError('That username is already taken.')
        # Return lowercased so allauth saves it correctly
        return val
