#!/usr/bin/env python3
"""End-to-end test script for the DigiLocker Issuer API.

Usage:
    source venv/bin/activate
    python manage.py runserver 8000    # in another terminal
    python test_e2e.py
"""

import base64
import hashlib
import hmac
import sys
from datetime import datetime, timezone, timedelta

import requests

BASE_URL = "http://127.0.0.1:8000"
API_KEY = "change-me-to-shared-secret"  # must match .env


def sign_body(body: bytes) -> str:
    return base64.b64encode(
        hmac.new(API_KEY.encode(), body, hashlib.sha256).digest()
    ).decode()


def make_keyhash(ts: str) -> str:
    return hashlib.sha256((API_KEY + ts).encode()).hexdigest()


def test_pull_uri():
    """Test the Pull URI Request API end-to-end."""
    print("=" * 60)
    print("TEST 1: Pull URI Request (valid, should return Status=1)")
    print("=" * 60)

    ist = timezone(timedelta(hours=5, minutes=30))
    ts = datetime.now(ist).strftime("%Y-%m-%dT%H:%M:%S+05:30")
    keyhash = make_keyhash(ts)

    body = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<PullURIRequest xmlns="http://tempuri.org/" ver="3.0"'
        f' ts="{ts}" txn="e2e-test-001"'
        f' orgId="in.nic.ngl.digilocker"'
        f' keyhash="{keyhash}" format="both">'
        f"<DocDetails>"
        f"<DocType>PPO</DocType>"
        f"<DigiLockerId>test-locker-id</DigiLockerId>"
        f"<FullName>Test User</FullName>"
        f"<DOB>01-01-1990</DOB>"
        f"<UDF1>AUTH001</UDF1>"
        f"</DocDetails>"
        f"</PullURIRequest>"
    ).encode()

    hmac_sig = sign_body(body)

    resp = requests.post(
        f"{BASE_URL}/issuer/pull-uri",
        data=body,
        headers={
            "Content-Type": "application/xml",
            "x-digilocker-hmac": hmac_sig,
        },
    )

    print(f"Status Code: {resp.status_code}")
    print(f"Response:\n{resp.text[:1000]}\n")

    if resp.status_code == 200 and b'Status="1"' in resp.content:
        print("PASS: Got success response with URI\n")
    else:
        print("FAIL: Expected Status=1\n")
        return False
    return True


def test_pull_uri_no_hmac():
    """Test that missing HMAC returns 401."""
    print("=" * 60)
    print("TEST 2: Pull URI without HMAC (should return 401)")
    print("=" * 60)

    body = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<PullURIRequest xmlns="http://tempuri.org/" ver="3.0"'
        b' ts="2024-01-01T00:00:00+05:30" txn="no-hmac"'
        b' orgId="in.nic.ngl.digilocker" keyhash="bad">'
        b"<DocDetails><DocType>PPO</DocType>"
        b"<DigiLockerId>x</DigiLockerId>"
        b"<UDF1>PPO123456</UDF1>"
        b"</DocDetails></PullURIRequest>"
    )

    resp = requests.post(
        f"{BASE_URL}/issuer/pull-uri",
        data=body,
        headers={"Content-Type": "application/xml"},
    )

    print(f"Status Code: {resp.status_code}")
    if resp.status_code == 401:
        print("PASS: Correctly rejected without HMAC\n")
    else:
        print(f"FAIL: Expected 401, got {resp.status_code}\n")
        return False
    return True


def test_pull_uri_wrong_doc():
    """Test that a non-existent document returns Status=0."""
    print("=" * 60)
    print("TEST 3: Pull URI for non-existent doc (should return Status=0)")
    print("=" * 60)

    ist = timezone(timedelta(hours=5, minutes=30))
    ts = datetime.now(ist).strftime("%Y-%m-%dT%H:%M:%S+05:30")
    keyhash = make_keyhash(ts)

    body = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<PullURIRequest xmlns="http://tempuri.org/" ver="3.0"'
        f' ts="{ts}" txn="e2e-test-003"'
        f' orgId="in.nic.ngl.digilocker"'
        f' keyhash="{keyhash}" format="both">'
        f"<DocDetails>"
        f"<DocType>PPO</DocType>"
        f"<DigiLockerId>test-locker</DigiLockerId>"
        f"<FullName>Nobody</FullName>"
        f"<DOB>01-01-2000</DOB>"
        f"<UDF1>DOESNOTEXIST</UDF1>"
        f"</DocDetails>"
        f"</PullURIRequest>"
    ).encode()

    hmac_sig = sign_body(body)

    resp = requests.post(
        f"{BASE_URL}/issuer/pull-uri",
        data=body,
        headers={
            "Content-Type": "application/xml",
            "x-digilocker-hmac": hmac_sig,
        },
    )

    print(f"Status Code: {resp.status_code}")
    print(f"Response:\n{resp.text[:500]}\n")

    if b'Status="0"' in resp.content:
        print("PASS: Got error response for missing document\n")
    else:
        print("FAIL: Expected Status=0\n")
        return False
    return True


def test_pull_uri_wrong_identity():
    """Test that wrong identity fields return Status=0."""
    print("=" * 60)
    print("TEST 4: Pull URI with wrong name (should return Status=0)")
    print("=" * 60)

    ist = timezone(timedelta(hours=5, minutes=30))
    ts = datetime.now(ist).strftime("%Y-%m-%dT%H:%M:%S+05:30")
    keyhash = make_keyhash(ts)

    body = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<PullURIRequest xmlns="http://tempuri.org/" ver="3.0"'
        f' ts="{ts}" txn="e2e-test-004"'
        f' orgId="in.nic.ngl.digilocker"'
        f' keyhash="{keyhash}" format="both">'
        f"<DocDetails>"
        f"<DocType>PPO</DocType>"
        f"<DigiLockerId>test-locker</DigiLockerId>"
        f"<FullName>Wrong Name</FullName>"
        f"<DOB>31-12-1990</DOB>"
        f"<UDF1>AUTH001</UDF1>"
        f"</DocDetails>"
        f"</PullURIRequest>"
    ).encode()

    hmac_sig = sign_body(body)

    resp = requests.post(
        f"{BASE_URL}/issuer/pull-uri",
        data=body,
        headers={
            "Content-Type": "application/xml",
            "x-digilocker-hmac": hmac_sig,
        },
    )

    print(f"Status Code: {resp.status_code}")
    if b'Status="0"' in resp.content:
        print("PASS: Correctly rejected wrong identity\n")
    else:
        print("FAIL: Expected Status=0\n")
        return False
    return True


if __name__ == "__main__":
    print("\nDigiLocker Issuer API — End-to-End Tests")
    print("Targeting:", BASE_URL)
    print()

    # Need requests library
    try:
        import requests
    except ImportError:
        print("Installing requests...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "-q"])
        import requests

    results = []
    results.append(("Pull URI (valid)", test_pull_uri()))
    results.append(("Pull URI (no HMAC)", test_pull_uri_no_hmac()))
    results.append(("Pull URI (missing doc)", test_pull_uri_wrong_doc()))
    results.append(("Pull URI (wrong identity)", test_pull_uri_wrong_identity()))

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print("All tests passed!")
    else:
        print("Some tests failed.")
        sys.exit(1)
