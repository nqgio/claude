"""eBay Marketplace Account Deletion/Closure notifications (required for production keys).

This app stores eBay buyer names/addresses for order fulfillment, so it does not
qualify for the "I don't persist eBay data" exemption; it implements the endpoint:
  * GET  ?challenge_code=...  → {"challengeResponse": sha256(code + token + endpoint)}
  * POST notification         → verify eBay's signature, then erase that user's data
It is served on a separate port (APP_NOTIFY_PORT, default 8001) so that a public
tunnel to it never exposes the dashboard.
"""
from __future__ import annotations

import base64
import functools
import hashlib
import json

import httpx
from fastapi import FastAPI, HTTPException, Request, Response

from .. import activity, config
from ..db import session_scope
from ..models import Order
from . import client

PATH = "/ebay/account-deletion"


def challenge_response(challenge_code: str, verification_token: str, endpoint: str) -> str:
    h = hashlib.sha256()
    h.update(challenge_code.encode())
    h.update(verification_token.encode())
    h.update(endpoint.encode())
    return h.hexdigest()


@functools.lru_cache(maxsize=16)
def _public_key(kid: str) -> str:
    tok = client.app_token("production")
    r = httpx.get(f"https://api.ebay.com/commerce/notification/v1/public_key/{kid}",
                  headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    r.raise_for_status()
    return r.json()["key"]


def _pem(key: str) -> bytes:
    body = key.replace("-----BEGIN PUBLIC KEY-----", "").replace("-----END PUBLIC KEY-----", "").strip()
    body = "".join(body.split())
    lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    return ("-----BEGIN PUBLIC KEY-----\n" + "\n".join(lines) + "\n-----END PUBLIC KEY-----\n").encode()


def verify_signature(header: str, body: bytes) -> bool:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    sig = json.loads(base64.b64decode(header))
    pub = serialization.load_pem_public_key(_pem(_public_key(sig["kid"])))
    try:
        pub.verify(base64.b64decode(sig["signature"]), body, ec.ECDSA(hashes.SHA1()))
        return True
    except InvalidSignature:
        return False


def erase_user(username: str) -> int:
    n = 0
    with session_scope() as s:
        for o in s.query(Order).filter(Order.buyer_username == username).all():
            o.buyer_username = "[deleted]"
            o.ship_name = o.ship_line1 = o.ship_line2 = o.ship_phone = "[deleted]"
            o.ship_city = o.ship_state = o.ship_postal = ""
            o.raw = None
            n += 1
    return n


def build_app() -> FastAPI:
    app = FastAPI(title="eBay notifications", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get(PATH)
    def challenge(challenge_code: str):
        token, endpoint = config.env("EBAY_VERIFICATION_TOKEN"), config.env("EBAY_DELETION_ENDPOINT_URL")
        if not token or not endpoint:
            raise HTTPException(500, "EBAY_VERIFICATION_TOKEN / EBAY_DELETION_ENDPOINT_URL not set in .env")
        return {"challengeResponse": challenge_response(challenge_code, token, endpoint)}

    @app.post(PATH)
    async def notification(request: Request):
        body = await request.body()
        sig = request.headers.get("x-ebay-signature", "")
        try:
            ok = bool(sig) and verify_signature(sig, body)
        except Exception as exc:  # key fetch failure etc. — let eBay retry later
            activity.warning("ebay", f"Could not verify account-deletion notification: {exc}")
            return Response(status_code=500)
        if not ok:
            return Response(status_code=412)
        data = (json.loads(body).get("notification") or {}).get("data") or {}
        username = data.get("username", "")
        n = erase_user(username) if username else 0
        activity.info("ebay", f"eBay account deletion notice processed: erased data on {n} order(s)")
        return Response(status_code=204)

    @app.get("/")
    def root():
        return {"ok": True}

    return app
