"""Tests for admin and manage console IP allowlist middleware."""

from django.test import RequestFactory, TestCase, override_settings

from config.middleware.ip_allowlist import RestrictedAdminIPMiddleware
from config.ip_allowlist import get_client_ip, ip_is_allowed, parse_ip_allowlist


class IpAllowlistHelpersTest(TestCase):
    def test_parse_single_ip_and_cidr(self):
        allowed = parse_ip_allowlist(["127.0.0.1", "10.0.0.0/8"])
        self.assertTrue(ip_is_allowed("127.0.0.1", allowed))
        self.assertTrue(ip_is_allowed("10.1.2.3", allowed))
        self.assertFalse(ip_is_allowed("8.8.8.8", allowed))

    def test_get_client_ip_honors_xff_when_trusted(self):
        request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="203.0.113.1, 10.0.0.1")
        self.assertEqual(
            get_client_ip(request, trust_x_forwarded_for=True),
            "203.0.113.1",
        )
        self.assertNotEqual(
            get_client_ip(request, trust_x_forwarded_for=False),
            "203.0.113.1",
        )


@override_settings(
    RESTRICTED_ADMIN_IP_ALLOWLIST=["127.0.0.1"],
    TRUST_X_FORWARDED_FOR=False,
)
class RestrictedAdminIPMiddlewareTest(TestCase):
    def setUp(self):
        self.middleware = RestrictedAdminIPMiddleware(lambda request: _ok_response())

    def test_allows_manage_from_allowlisted_ip(self):
        request = RequestFactory().get("/issuer/manage/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_blocks_manage_from_other_ip(self):
        request = RequestFactory().get("/issuer/manage/")
        request.META["REMOTE_ADDR"] = "203.0.113.50"
        response = self.middleware(request)
        self.assertEqual(response.status_code, 403)

    def test_blocks_django_admin_from_other_ip(self):
        request = RequestFactory().get("/admin/login/")
        request.META["REMOTE_ADDR"] = "203.0.113.50"
        response = self.middleware(request)
        self.assertEqual(response.status_code, 403)

    def test_allows_api_paths_without_restriction(self):
        request = RequestFactory().post("/api/pulluri")
        request.META["REMOTE_ADDR"] = "203.0.113.50"
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)


def _ok_response():
    from django.http import HttpResponse

    return HttpResponse("ok")
