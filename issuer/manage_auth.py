"""Authentication and authorization for the issuer management console."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import NON_FIELD_ERRORS
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_http_methods

from issuer.manage_forms import ManagePortalAuthenticationForm
from issuer.manage_login_security import (
    clear_failed_logins,
    get_failure_count,
    is_locked,
    record_failed_login,
)

MANAGE_PORTAL_PERMISSION = "issuer.access_manage_portal"
MANAGE_LOGIN_URL = reverse_lazy("issuer:manage-login")


def user_has_manage_portal_access(user) -> bool:
    return (
        user.is_authenticated
        and user.is_active
        and (user.is_superuser or user.has_perm(MANAGE_PORTAL_PERMISSION))
    )


def require_manage_portal(view_func):
    """Require login (redirect) and access_manage_portal permission (403 if missing)."""
    return login_required(login_url=MANAGE_LOGIN_URL)(
        permission_required(
            MANAGE_PORTAL_PERMISSION,
            raise_exception=True,
        )(view_func)
    )


class ManagePortalLoginView(LoginView):
    template_name = "issuer/manage/login.html"
    redirect_authenticated_user = True
    form_class = ManagePortalAuthenticationForm

    def dispatch(self, request, *args, **kwargs):
        locked, seconds_left = is_locked(request)
        if locked:
            minutes = max(1, (seconds_left + 59) // 60)
            self.login_status_message = (
                f"Too many failed sign-in attempts. Try again in about {minutes} "
                "minute(s)."
            )
            return self.render_to_response(self.get_context_data())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        failures = get_failure_count(self.request)
        max_failures = settings.MANAGE_LOGIN_MAX_FAILURES
        context["failed_attempts"] = failures
        context["max_failures"] = max_failures
        context["attempts_remaining"] = max(0, max_failures - failures)
        context["lockout_minutes"] = settings.MANAGE_LOGIN_LOCKOUT_MINUTES
        context["login_status_message"] = getattr(
            self,
            "login_status_message",
            "",
        )
        return context

    def get_success_url(self):
        return reverse("issuer:manage-hub")

    def form_invalid(self, form):
        if not form.has_error(NON_FIELD_ERRORS, "invalid_login"):
            return super().form_invalid(form)

        count = get_failure_count(self.request)
        max_failures = settings.MANAGE_LOGIN_MAX_FAILURES
        if count >= max_failures:
            self.login_status_message = (
                f"Too many failed sign-in attempts. This location is locked for "
                f"{settings.MANAGE_LOGIN_LOCKOUT_MINUTES} minutes."
            )
        else:
            remaining = max_failures - count
            self.login_status_message = (
                f"Sign-in failed. {count} of {max_failures} failed attempts; "
                f"{remaining} attempt(s) remaining before a "
                f"{settings.MANAGE_LOGIN_LOCKOUT_MINUTES}-minute lockout."
            )
        return super().form_invalid(form)

    def form_valid(self, form):
        response = super().form_valid(form)
        if not user_has_manage_portal_access(self.request.user):
            logout(self.request)
            record_failed_login(self.request)
            messages.error(
                self.request,
                "This account does not have access to the management console. "
                "Ask an administrator to grant the “access manage portal” permission.",
            )
            return redirect("issuer:manage-login")
        clear_failed_logins(self.request)
        return response


@require_http_methods(["GET", "POST"])
def manage_logout(request):
    logout(request)
    return redirect("issuer:manage-login")
