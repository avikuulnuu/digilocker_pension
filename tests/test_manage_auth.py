"""Tests for management console authentication and authorization."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from issuer.models import AccessLog, Document

User = get_user_model()


def grant_manage_portal(user):
    perm = Permission.objects.get(
        codename="access_manage_portal",
        content_type=ContentType.objects.get_for_model(Document),
    )
    user.user_permissions.add(perm)


@override_settings(CAPTCHA_TEST_MODE=True)
class ManagePortalAuthTest(TestCase):
    def _post_login(self, username, password, *, follow=False):
        return self.client.post(
            self.login_url,
            {
                "username": username,
                "password": password,
                "captcha_0": "passed",
                "captcha_1": "passed",
            },
            follow=follow,
        )

    def setUp(self):
        cache.clear()
        self.hub_url = reverse("issuer:manage-hub")
        self.login_url = reverse("issuer:manage-login")

        self.authorized = User.objects.create_user(
            username="ops_user",
            password="test-pass-123",
        )
        grant_manage_portal(self.authorized)

        self.other = User.objects.create_user(
            username="no_access",
            password="test-pass-123",
        )

    def test_anonymous_manage_hub_redirects_to_login(self):
        response = self.client.get(self.hub_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/issuer/manage/login/", response["Location"])

    def test_user_without_permission_gets_403(self):
        self.client.force_login(self.other)
        response = self.client.get(self.hub_url)
        self.assertEqual(response.status_code, 403)

    def test_user_with_permission_can_access_hub(self):
        self.client.force_login(self.authorized)
        response = self.client.get(self.hub_url)
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_access_hub_without_explicit_permission(self):
        admin = User.objects.create_superuser(
            username="admin",
            email="admin@test",
            password="admin-pass-123",
        )
        self.client.force_login(admin)
        response = self.client.get(self.hub_url)
        self.assertEqual(response.status_code, 200)

    def test_login_without_permission_shows_error(self):
        response = self._post_login("no_access", "test-pass-123", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "does not have access to the management console",
        )
        self.assertFalse(self.client.session.get("_auth_user_id"))

    def test_login_with_permission_redirects_to_hub(self):
        response = self._post_login("ops_user", "test-pass-123")
        self.assertRedirects(response, self.hub_url, fetch_redirect_response=False)

    def test_logout_clears_session(self):
        self.client.force_login(self.authorized)
        response = self.client.post(reverse("issuer:manage-logout"))
        self.assertRedirects(response, self.login_url, fetch_redirect_response=False)
        response = self.client.get(self.hub_url)
        self.assertEqual(response.status_code, 302)


@override_settings(CAPTCHA_TEST_MODE=True)
class ManagePortalReadOnlyTest(TestCase):
    """Data views under /issuer/manage/ must not accept mutating HTTP methods."""

    READ_ONLY_GET_URLS = (
        "issuer:manage-hub",
        "issuer:document-list",
        "issuer:document-export",
        "issuer:accesslog-list",
        "issuer:accesslog-export",
        "issuer:integritylog-list",
        "issuer:integritylog-export",
        "issuer:kpi-report",
        "issuer:kpi-report-download",
    )

    def setUp(self):
        self.user = User.objects.create_user(username="ops", password="test-pass-123")
        grant_manage_portal(self.user)
        self.client.force_login(self.user)

    def test_mutating_methods_rejected_on_data_views(self):
        for url_name in self.READ_ONLY_GET_URLS:
            url = reverse(url_name)
            for method in ("post", "put", "patch", "delete"):
                response = getattr(self.client, method)(url)
                self.assertEqual(
                    response.status_code,
                    405,
                    msg=f"{method.upper()} {url_name} should be read-only",
                )


@override_settings(CAPTCHA_TEST_MODE=True)
class ManagePortalCopyTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="portal_copy_user",
            password="test-pass-123",
        )
        grant_manage_portal(self.user)
        self.client.force_login(self.user)

    def test_list_pages_show_meaningful_subheaders(self):
        expected_copy = {
            "issuer:document-list": "All existing pension documents.",
            "issuer:accesslog-list": "All access attempts from DigiLocker.",
            "issuer:integritylog-list": "Logs of all document integrity events.",
        }

        for url_name, text in expected_copy.items():
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertContains(response, text)

    def test_success_status_has_explanation_on_access_log_pages(self):
        access_log = AccessLog.objects.create(response_status=1, txn_id="txn-success")

        for url in (
            reverse("issuer:manage-hub"),
            reverse("issuer:accesslog-list"),
            reverse("issuer:accesslog-detail", kwargs={"pk": access_log.pk}),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, "1 (Successfully responded)")

    def test_status_zero_detail_remains_raw_with_error_message(self):
        access_log = AccessLog.objects.create(
            response_status=0,
            txn_id="txn-not-served",
            error_message="Invalid request value",
        )

        response = self.client.get(
            reverse("issuer:accesslog-detail", kwargs={"pk": access_log.pk})
        )

        self.assertContains(response, "<dt>Response status</dt><dd>0</dd>", html=True)
        self.assertContains(response, "<dt>Error message</dt><dd>Invalid request value</dd>", html=True)
