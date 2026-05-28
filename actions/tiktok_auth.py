"""
TikTok OAuth 2.0 Authorization Code Flow with PKCE
Handles one-time login, token storage, and auto-refresh for JARVIS.
"""

import os
import json
import time
import hashlib
import base64
import secrets
import webbrowser
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
import requests


class TikTokAuth:
    """Manages TikTok OAuth2 tokens for the Content Posting API."""

    AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
    TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
    SCOPES = "user.info.basic,video.publish,video.upload"
    REDIRECT_PORT = 5588
    REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"

    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.token_file = self.base_dir / "memory" / "tiktok_tokens.json"

        # Load client credentials from api_keys.json
        keys_path = self.base_dir / "config" / "api_keys.json"
        if keys_path.exists():
            with open(keys_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            tiktok_cfg = config.get("tiktok", {})
            self.client_key = tiktok_cfg.get("client_key", "")
            self.client_secret = tiktok_cfg.get("client_secret", "")
            redirect = tiktok_cfg.get("redirect_uri", "")
            if redirect:
                self.REDIRECT_URI = redirect
                parsed = urlparse(redirect)
                self.REDIRECT_PORT = parsed.port or 5588
        else:
            self.client_key = ""
            self.client_secret = ""

        self._tokens = self._load_tokens()

    # ------------------------------------------------------------------ #
    #  PKCE helpers                                                        #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _generate_code_verifier():
        """Generate a random code_verifier (43-128 chars, URL-safe)."""
        return secrets.token_urlsafe(64)[:128]

    @staticmethod
    def _generate_code_challenge(verifier):
        """S256 code_challenge from code_verifier."""
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    # ------------------------------------------------------------------ #
    #  Token persistence                                                   #
    # ------------------------------------------------------------------ #
    def _load_tokens(self):
        if self.token_file.exists():
            with open(self.token_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_tokens(self, data):
        self._tokens = data
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # ------------------------------------------------------------------ #
    #  Authorization URL                                                   #
    # ------------------------------------------------------------------ #
    def get_auth_url(self):
        """Build the TikTok authorization URL with PKCE."""
        code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(code_verifier)
        state = secrets.token_hex(16)

        params = {
            "client_key": self.client_key,
            "scope": self.SCOPES,
            "response_type": "code",
            "redirect_uri": self.REDIRECT_URI,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        url = f"{self.AUTH_URL}?{urlencode(params)}"
        return url, code_verifier, state

    # ------------------------------------------------------------------ #
    #  Local callback server                                               #
    # ------------------------------------------------------------------ #
    def authorize_interactive(self):
        """
        Opens the browser for one-time TikTok login.
        Starts a temporary local HTTP server to catch the OAuth callback.
        Returns True on success.
        """
        auth_url, code_verifier, state = self.get_auth_url()
        result = {"code": None, "error": None}

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                qs = parse_qs(urlparse(self.path).query)
                if "code" in qs:
                    result["code"] = qs["code"][0]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        b"<html><body style='background:#0a0e17;color:#38bdf8;"
                        b"font-family:system-ui;display:flex;justify-content:center;"
                        b"align-items:center;height:100vh;margin:0;'>"
                        b"<h1>JARVIS authorized! You can close this tab.</h1>"
                        b"</body></html>"
                    )
                else:
                    result["error"] = qs.get("error", ["unknown"])[0]
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Authorization failed.")

            def log_message(self, format, *args):
                pass  # suppress log noise

        server = HTTPServer(("localhost", self.REDIRECT_PORT), CallbackHandler)
        server.timeout = 120  # wait up to 2 minutes

        print("[TikTokAuth] Opening browser for TikTok login...")
        webbrowser.open(auth_url)

        # Handle one request (the callback)
        server.handle_request()
        server.server_close()

        if result["code"]:
            print("[TikTokAuth] Authorization code received. Exchanging for tokens...")
            return self._exchange_code(result["code"], code_verifier)
        else:
            print(f"[TikTokAuth] Authorization failed: {result['error']}")
            return False

    # ------------------------------------------------------------------ #
    #  Token exchange                                                      #
    # ------------------------------------------------------------------ #
    def _exchange_code(self, code, code_verifier):
        """Exchange authorization code for access + refresh tokens."""
        payload = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.REDIRECT_URI,
            "code_verifier": code_verifier,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            resp = requests.post(self.TOKEN_URL, data=payload, headers=headers, timeout=15)
            data = resp.json()

            if "access_token" in data:
                token_data = {
                    "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token", ""),
                    "open_id": data.get("open_id", ""),
                    "expires_in": data.get("expires_in", 86400),
                    "refresh_expires_in": data.get("refresh_expires_in", 0),
                    "obtained_at": int(time.time()),
                    "scope": data.get("scope", ""),
                }
                self._save_tokens(token_data)
                print("[TikTokAuth] Tokens saved successfully.")
                return True
            else:
                print(f"[TikTokAuth] Token exchange failed: {data}")
                return False

        except Exception as e:
            print(f"[TikTokAuth] Token exchange error: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  Token refresh                                                       #
    # ------------------------------------------------------------------ #
    def _refresh_access_token(self):
        """Use the refresh_token to get a new access_token."""
        if not self._tokens.get("refresh_token"):
            print("[TikTokAuth] No refresh token available. Re-authorization needed.")
            return False

        payload = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self._tokens["refresh_token"],
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            resp = requests.post(self.TOKEN_URL, data=payload, headers=headers, timeout=15)
            data = resp.json()

            if "access_token" in data:
                self._tokens["access_token"] = data["access_token"]
                self._tokens["refresh_token"] = data.get("refresh_token", self._tokens["refresh_token"])
                self._tokens["expires_in"] = data.get("expires_in", 86400)
                self._tokens["obtained_at"] = int(time.time())
                self._save_tokens(self._tokens)
                print("[TikTokAuth] Token refreshed successfully.")
                return True
            else:
                print(f"[TikTokAuth] Token refresh failed: {data}")
                return False

        except Exception as e:
            print(f"[TikTokAuth] Token refresh error: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  Public API: get a valid token                                       #
    # ------------------------------------------------------------------ #
    def get_valid_token(self):
        """
        Returns a valid access_token string.
        Auto-refreshes if expired.
        Triggers interactive login if no tokens exist.
        Returns None if all attempts fail.
        """
        if not self._tokens.get("access_token"):
            print("[TikTokAuth] No tokens found. Starting first-time authorization...")
            if not self.authorize_interactive():
                return None
            return self._tokens.get("access_token")

        # Check if token is expired (with 5-min buffer)
        obtained = self._tokens.get("obtained_at", 0)
        expires_in = self._tokens.get("expires_in", 86400)
        if time.time() > obtained + expires_in - 300:
            print("[TikTokAuth] Token expired or expiring soon. Refreshing...")
            if self._refresh_access_token():
                return self._tokens["access_token"]
            else:
                # Refresh failed — try full re-auth
                print("[TikTokAuth] Refresh failed. Attempting re-authorization...")
                if self.authorize_interactive():
                    return self._tokens.get("access_token")
                return None

        return self._tokens["access_token"]

    def get_open_id(self):
        """Returns the stored TikTok open_id."""
        return self._tokens.get("open_id", "")

    @property
    def is_authorized(self):
        """Check if we have stored tokens."""
        return bool(self._tokens.get("access_token"))


if __name__ == "__main__":
    auth = TikTokAuth()
    token = auth.get_valid_token()
    if token:
        print(f"[TikTokAuth] Got valid token: {token[:20]}...")
    else:
        print("[TikTokAuth] Failed to get token.")
