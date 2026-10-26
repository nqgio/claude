"""Low-level eBay REST client: OAuth 2.0 (user + application tokens with
automatic refresh), rate limiting, retries, and a hard dry-run guard that
refuses any write call while dry-run mode is on."""
from __future__ import annotations

import base64
import secrets
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from .. import activity, config
from .. import settings_store as st

SCOPES = [
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.marketing",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
    "https://api.ebay.com/oauth/api_scope/sell.finances",
    "https://api.ebay.com/oauth/api_scope/sell.analytics.readonly",
]
APP_SCOPE = "https://api.ebay.com/oauth/api_scope"

HOSTS = {
    "sandbox": {"api": "https://api.sandbox.ebay.com", "apiz": "https://apiz.sandbox.ebay.com",
                "auth": "https://auth.sandbox.ebay.com/oauth2/authorize"},
    "production": {"api": "https://api.ebay.com", "apiz": "https://apiz.ebay.com",
                   "auth": "https://auth.ebay.com/oauth2/authorize"},
}

# Requests per second per API family; eBay's daily call limits are far above what
# this app makes, but we still pace calls and honor 429 Retry-After.
RATE_PER_SEC = {"default": 4.0, "finances": 2.0, "analytics": 1.0, "trading": 2.0}


class EbayError(Exception):
    def __init__(self, message: str, status: int | None = None, body: object = None):
        super().__init__(message)
        self.status = status
        self.body = body


class EbayNotConnected(EbayError):
    pass


class DryRunBlocked(EbayError):
    pass


class _RateLimiter:
    def __init__(self):
        self.next_ok: dict[str, float] = defaultdict(float)
        self.lock = threading.Lock()
        self.daily: dict[str, int] = defaultdict(int)
        self.day = datetime.now().date()

    def wait(self, family: str) -> None:
        with self.lock:
            today = datetime.now().date()
            if today != self.day:
                self.daily.clear()
                self.day = today
            self.daily[family] += 1
            now = time.monotonic()
            slot = max(now, self.next_ok[family])
            self.next_ok[family] = slot + 1.0 / RATE_PER_SEC.get(family, RATE_PER_SEC["default"])
        if slot > now:
            time.sleep(slot - now)


_limiter = _RateLimiter()
_token_lock = threading.Lock()
_tokens: dict[tuple[str, str], tuple[str, float]] = {}  # (env, kind) -> (token, expires_monotonic)
_oauth_states: dict[str, float] = {}


def _env() -> str:
    return st.get("ebay_environment")


def keys(environment: str | None = None) -> dict:
    return config.ebay_keys(environment or _env())


def _basic(environment: str) -> str:
    k = keys(environment)
    if not k["app_id"] or not k["cert_id"]:
        raise EbayNotConnected(f"eBay {environment} App ID / Cert ID missing in .env")
    return "Basic " + base64.b64encode(f"{k['app_id']}:{k['cert_id']}".encode()).decode()


def _token_url(environment: str) -> str:
    return HOSTS[environment]["api"] + "/identity/v1/oauth2/token"


def _post_token(environment: str, data: dict) -> dict:
    with httpx.Client(timeout=30, transport=_transport) as c:
        r = c.post(_token_url(environment), data=data,
                   headers={"Authorization": _basic(environment), "Content-Type": "application/x-www-form-urlencoded"})
    if r.status_code != 200:
        raise EbayError(f"eBay token request failed ({r.status_code}): {r.text[:300]}", r.status_code, r.text)
    return r.json()


# ---- OAuth consent flow ------------------------------------------------------------

def consent_url(environment: str | None = None) -> str:
    environment = environment or _env()
    k = keys(environment)
    if not k["app_id"] or not k["runame"]:
        raise EbayNotConnected(f"Set the eBay {environment} App ID and RuName in .env first")
    state = secrets.token_urlsafe(16)
    _oauth_states[state] = time.time()
    q = {"client_id": k["app_id"], "redirect_uri": k["runame"], "response_type": "code",
         "scope": " ".join(SCOPES), "state": state, "prompt": "login"}
    return HOSTS[environment]["auth"] + "?" + urlencode(q)


def extract_code(value: str) -> tuple[str, str | None]:
    """Accept either a raw authorization code or the full redirect URL eBay sent you to."""
    value = value.strip()
    if value.startswith("http"):
        q = parse_qs(urlparse(value).query)
        if "code" not in q:
            raise EbayError("That URL has no 'code=' parameter — copy the address bar after clicking 'I agree'.")
        return q["code"][0], (q.get("state") or [None])[0]
    return value, None


def exchange_code(code: str, environment: str | None = None, state: str | None = None) -> dict:
    environment = environment or _env()
    if state is not None and state not in _oauth_states:
        activity.warning("ebay", "OAuth state not recognized (app restarted mid-flow?) — continuing with code exchange")
    _oauth_states.pop(state or "", None)
    data = _post_token(environment, {"grant_type": "authorization_code", "code": code,
                                     "redirect_uri": keys(environment)["runame"]})
    config.save_env_value(config.ebay_prefix(environment) + "REFRESH_TOKEN", data["refresh_token"])
    expires = (datetime.now(timezone.utc) + timedelta(seconds=int(data.get("refresh_token_expires_in", 0)))).isoformat()
    exp = dict(st.get("ebay_refresh_token_expires") or {})
    exp[environment] = expires
    st.set_internal("ebay_refresh_token_expires", exp)
    with _token_lock:
        _tokens[(environment, "user")] = (data["access_token"], time.monotonic() + int(data["expires_in"]) - 120)
    activity.info("ebay", f"Connected to eBay ({environment}); refresh token saved to .env")
    return {"environment": environment, "refresh_token_expires": expires}


def disconnect(environment: str | None = None) -> None:
    environment = environment or _env()
    config.save_env_value(config.ebay_prefix(environment) + "REFRESH_TOKEN", "")
    with _token_lock:
        _tokens.pop((environment, "user"), None)
    activity.info("ebay", f"Disconnected eBay ({environment})")


def user_token(environment: str | None = None) -> str:
    environment = environment or _env()
    with _token_lock:
        tok = _tokens.get((environment, "user"))
        if tok and tok[1] > time.monotonic():
            return tok[0]
        refresh = keys(environment)["refresh_token"]
        if not refresh:
            raise EbayNotConnected(f"eBay {environment} is not connected (Settings → Connect eBay)")
        data = _post_token(environment, {"grant_type": "refresh_token", "refresh_token": refresh,
                                         "scope": " ".join(SCOPES)})
        _tokens[(environment, "user")] = (data["access_token"], time.monotonic() + int(data["expires_in"]) - 120)
        return data["access_token"]


def app_token(environment: str | None = None) -> str:
    environment = environment or _env()
    with _token_lock:
        tok = _tokens.get((environment, "app"))
        if tok and tok[1] > time.monotonic():
            return tok[0]
        data = _post_token(environment, {"grant_type": "client_credentials", "scope": APP_SCOPE})
        _tokens[(environment, "app")] = (data["access_token"], time.monotonic() + int(data["expires_in"]) - 120)
        return data["access_token"]


def is_connected(environment: str | None = None) -> bool:
    return bool(keys(environment)["refresh_token"])


# ---- request ------------------------------------------------------------------------

_transport: httpx.BaseTransport | None = None  # tests inject httpx.MockTransport here


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _transport
    _transport = transport


def request(method: str, path: str, *, json: object = None, params: dict | None = None, family: str = "default",
            host: str = "api", token: str = "user", write: bool | None = None, headers: dict | None = None,
            content: bytes | str | None = None, environment: str | None = None, retries: int = 4) -> httpx.Response:
    """Make an eBay API call. `write` defaults to True for POST/PUT/DELETE; write calls
    are refused while dry-run is on."""
    environment = environment or _env()
    is_write = method.upper() in ("POST", "PUT", "DELETE") if write is None else write
    if is_write and st.get("dry_run"):
        raise DryRunBlocked(f"dry-run is ON — blocked {method} {path}")
    url = HOSTS[environment][host] + path
    attempt = 0
    refreshed = False
    while True:
        attempt += 1
        tok = user_token(environment) if token == "user" else app_token(environment)
        h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json", "Accept": "application/json",
             "Content-Language": "en-US", "Accept-Language": "en-US",
             "X-EBAY-C-MARKETPLACE-ID": st.get("marketplace_id")}
        if headers:
            h.update(headers)
        _limiter.wait(family)
        try:
            with httpx.Client(timeout=60, transport=_transport) as c:
                r = c.request(method, url, json=json, params=params, headers=h, content=content)
        except httpx.HTTPError as exc:
            if attempt <= retries:
                time.sleep(min(60, 2 ** attempt))
                continue
            raise EbayError(f"network error calling eBay {path}: {exc}") from exc
        if r.status_code == 401 and token == "user" and not refreshed:
            with _token_lock:
                _tokens.pop((environment, "user"), None)
            refreshed = True
            continue
        if r.status_code in (429, 500, 502, 503, 504) and attempt <= retries:
            wait = float(r.headers.get("Retry-After") or min(120, 2 ** attempt * 2))
            if r.status_code == 429:
                activity.warning("ebay", f"eBay rate limit hit on {path}; waiting {wait:.0f}s")
            time.sleep(wait)
            continue
        if r.status_code >= 400:
            try:
                body = r.json()
                msgs = "; ".join(e.get("longMessage") or e.get("message", "") for e in body.get("errors", [])) or r.text
            except ValueError:
                body, msgs = r.text, r.text
            raise EbayError(f"eBay {method} {path} failed ({r.status_code}): {msgs[:600]}", r.status_code, body)
        return r


def get_json(path: str, **kw) -> dict:
    r = request("GET", path, **kw)
    return r.json() if r.content else {}
