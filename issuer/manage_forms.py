"""Forms for the issuer management console."""

from django.contrib.auth.forms import AuthenticationForm
from captcha.fields import CaptchaField


class ManagePortalAuthenticationForm(AuthenticationForm):
    captcha = CaptchaField(label="Security check")
