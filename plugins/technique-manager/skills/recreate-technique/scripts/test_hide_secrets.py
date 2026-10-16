#!/usr/bin/env python3
"""Offline checks for hide_secrets.py: what it hides, what it leaves alone, and that nothing it
reports carries a value.

    python3 skills/recreate-technique/scripts/test_hide_secrets.py

Every value here is made up (this plugin is public). Token-shaped values are joined from pieces
at run time, so the repo's own secret scan does not mistake this file for a leak.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hide_secrets  # noqa: E402
import scan_privacy  # noqa: E402
from hide_secrets import hide, hide_counted  # noqa: E402

J = "".join
FAKE = {
    "aws key": J(["AK", "IA", "QWERTYUIOPASDFGH"]),
    "github token": J(["gh", "p_", "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"]),
    "slack token": J(["xo", "xb-", "1234567890-abcdefghijkl"]),
    "api key": J(["sk", "-ant-", "abcDEF123ghiJKL456mnoPQR789"]),
    "google key": J(["AI", "za", "Sy0123456789abcdefghijABCDEFGHIJ_-x"]),
    "jwt": J(["ey", "JhbGciOiJIUzI1NiJ9.", "ey", "JzdWIiOiIxMjM0In0.", "c2lnbmF0dXJlLWhlcmU"]),
}


class Hides(unittest.TestCase):
    def test_known_token_formats(self):
        for kind, value in FAKE.items():
            with self.subTest(kind=kind):
                out, seen = hide_counted(f"use {value} here")
                self.assertNotIn(value, out)
                self.assertEqual(seen[kind], 1, out)

    def test_bearer_url_password_and_private_key(self):
        bearer = "Authorization: Bearer " + J(["abcd", "EFGH", "1234", "ijkl", "MNOP"])
        self.assertIn("[hidden bearer token]", hide(bearer))
        url = "postgres://bob:" + "tr0ub4dor" + "@db.example.com/app"
        self.assertEqual(hide(url), "postgres://[hidden url password]@db.example.com/app")
        block = J(["-----BEGIN ", "RSA PRIVATE KEY-----\nMIIabc\n-----END ", "RSA PRIVATE KEY-----"])
        self.assertEqual(hide(f"key:\n{block}\ndone"), "key:\n[hidden private key]\ndone")

    def test_labelled_values_keep_their_label(self):
        cases = {
            "password: Tr0ub4dor&3": "password: [hidden labelled secret]",
            "STOREFRONT_PASSWORD='opensesame'": "STOREFRONT_PASSWORD='[hidden labelled secret]'",
            '"client_secret": "made-up-value"': '"client_secret": "[hidden labelled secret]"',
            'data-api-key="9f3k2-x81"': 'data-api-key="[hidden labelled secret]"',
            "the passphrase is Blue7Horse": "the passphrase is [hidden labelled secret]",
        }
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(hide(text), want)

    def test_generated_password_and_long_key(self):
        for word in ("xK9#mP2$vL7qR4", J(["aB3dE5gH7j", "K9mN1pQ3sT", "5vW7yZ9bC1"])):
            with self.subTest(shape=hide_secrets.shape(word)):
                self.assertEqual(hide(f"it is {word} now"), "it is [hidden random-looking word] now")


class LeavesAlone(unittest.TestCase):
    def test_prose_and_test_output(self):
        for text in ("the password is stored in the keychain",
                     "no real secret was involved.",
                     "PASS: 12 tests, 0 failed",
                     "DashPass is cheaper than LastPass",
                     "the build passed: everything",
                     "Secrets: none"):
            with self.subTest(text=text):
                self.assertEqual(hide(text), text)

    def test_pointers_to_secrets(self):
        for text in ("password: $DB_PASSWORD",
                     "api_key=os.environ['API_KEY']",
                     "SHOPIFY_ACCESS_TOKEN=<your token>",
                     "secret: ${{ secrets.DEPLOY }}",
                     "password: ********"):
            with self.subTest(text=text):
                self.assertEqual(hide(text), text)

    def test_ids_paths_times_and_names(self):
        for word in ("/Users/someone/Workspace/git/example-app/src/ServerMain2.ts",
                     "3f9a1c2e7b4d8f6a0c5e9b2d7f1a3c8e6b4d2f0a",
                     "123e4567-e89b-12d3-a456-426614174000",
                     "2026-10-08T19:30:49.835Z",
                     "msg_01AbCdEfGhIjKlMnOpQrStUv",
                     "toolu_01XyZaBcDeFgHiJkLmNoPqRs",
                     "fetchContextForSpec2",
                     "SHOPIFY_THEME_ACCESS_PASSWORD",
                     "color:#1A2B3C",
                     "**Tasks**12",
                     "11h4:30PM",
                     "example-app.config.json"):
            with self.subTest(word=word):
                self.assertEqual(hide(word), word)


class ReportsNoValues(unittest.TestCase):
    def test_found_holds_outlines(self):
        found = []
        hide_counted("password: Tr0ub4dor&3 and " + FAKE["aws key"], found)
        self.assertEqual(found, [("aws key", "AAAAAAAAAAAAAAAAAAAA"), ("labelled secret", "Aa9aa9aaa#9")])

    def test_privacy_scan_shows_outline_only(self):
        spec = {"blocks": [{"type": "user_prompt", "text": "my password: Tr0ub4dor&3"}]}
        hits = [h for h in scan_privacy.scan(spec) if h["kind"] == "secret"]
        self.assertEqual(len(hits), 1)
        self.assertNotIn("Tr0ub4dor", json.dumps(hits))
        self.assertIn("Aa9aa9aaa#9", hits[0]["match"])

    def test_audit_skips_signatures_and_prints_no_values(self):
        rec = {"timestamp": "2026-10-08T19:30:00Z", "message": {"content": [
            {"type": "thinking", "thinking": "ok", "signature": J(["Eq", "Rk9xK2mP4vL7qR4aB3dE5gH7jK9mN1"])},
            {"type": "text", "text": "password: Tr0ub4dor&3"}]}}
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "s.jsonl"
            f.write_text(json.dumps(rec) + "\n")
            out = hide_secrets.audit([f], None, None, show_hidden=True)
        self.assertEqual(out["hidden"], {"labelled secret": 1})
        self.assertNotIn("Tr0ub4dor", json.dumps(out))


if __name__ == "__main__":
    unittest.main()
