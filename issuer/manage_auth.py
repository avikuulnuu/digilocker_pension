"""Authentication and authorization for the issuer management console."""

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_http_methods

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

    def get_success_url(self):
        return reverse("issuer:manage-hub")

    def form_valid(self, form):
        response = super().form_valid(form)
        if not user_has_manage_portal_access(self.request.user):
            logout(self.request)
            messages.error(
                self.request,
                "This account does not have access to the management console. "
                "Ask an administrator to grant the “access manage portal” permission.",
            )
            return redirect("issuer:manage-login")
        return response


@require_http_methods(["GET", "POST"])
def manage_logout(request):
    logout(request)
    return redirect("issuer:manage-login")
