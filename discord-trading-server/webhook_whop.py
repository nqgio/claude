"""
Whop payment / membership integration — the recommended way to sell and verify
paid access for this server.

How it fits together:

    Buyer checks out on your Whop storefront
        -> Whop fires a webhook to this endpoint
        -> we map the Whop plan -> Discord tier (config.WHOP_PLAN_TIERS)
        -> we write data/subscriptions.json (shared with the bot)
        -> bot.py's sync loop assigns/removes the Discord role within ~2 min.

Linking a purchase to a Discord user:
    Whop's native Discord integration asks buyers to connect their Discord
    account, and the membership payload then carries it under `data.discord.id`.
    Make sure the Whop product has the Discord integration enabled (or collect
    the Discord ID and pass it in the membership `metadata`).

Events handled:
    membership.went_valid    -> grant the tier
    membership.went_invalid  -> revoke (cancellation, refund, failed renewal)

Setup:
    1. Fill WHOP_PLAN_TIERS and WHOP_STORE_URL in config.py.
    2. Set WHOP_WEBHOOK_SECRET in .env (from your Whop webhook settings).
    3. Deploy this endpoint (e.g. https://yourhost/whop/webhook) and register it
       in Whop -> Developer / Webhooks for the two events above.

NOTE: Whop's exact signature scheme and payload keys can change between API
versions — the verification + field access here follow the common v2/v5 shape
and are easy to adjust. Confirm against https://docs.whop.com if a field is
missing in your payloads.
"""

import hashlib
import hmac
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, request, abort

import config

load_dotenv()

WHOP_WEBHOOK_SECRET = os.getenv("WHOP_WEBHOOK_SECRET", "")
# Header Whop uses to sign the request body. Adjust if your Whop version differs.
WHOP_SIGNATURE_HEADER = os.getenv("WHOP_SIGNATURE_HEADER", "X-Whop-Signature")
GUILD_ID = os.getenv("GUILD_ID", "0")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
SUBS_FILE = DATA_DIR / "subscriptions.json"

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Shared subscription store (the bot reads the same file).
# ---------------------------------------------------------------------------
def _load():
    return json.loads(SUBS_FILE.read_text()) if SUBS_FILE.exists() else {}


def _save(subs):
    SUBS_FILE.write_text(json.dumps(subs, indent=2))


def grant(discord_id, tier):
    subs = _load()
    # Whop manages the renewal lifecycle, so no local expiry: a went_invalid
    # event removes access. expires=None keeps the bot from auto-expiring it.
    subs.setdefault(str(GUILD_ID), {})[str(discord_id)] = {"tier": tier, "expires": None}
    _save(subs)
    print(f"[whop] granted {tier} -> discord:{discord_id}")


def revoke(discord_id):
    subs = _load()
    if subs.get(str(GUILD_ID), {}).pop(str(discord_id), None) is not None:
        _save(subs)
        print(f"[whop] revoked -> discord:{discord_id}")


# ---------------------------------------------------------------------------
# Webhook security + parsing
# ---------------------------------------------------------------------------
def verify_signature(raw_body, header_value):
    """HMAC-SHA256 of the raw body with the webhook secret. Only enforced when
    a secret is configured."""
    if not WHOP_WEBHOOK_SECRET:
        return True  # not configured -> skip (set the secret in production!)
    if not header_value:
        return False
    digest = hmac.new(WHOP_WEBHOOK_SECRET.encode(),
                      raw_body, hashlib.sha256).hexdigest()
    # Accept either a bare hex digest or a "sha256=" prefixed one.
    candidate = header_value.split("=", 1)[-1].strip()
    return hmac.compare_digest(digest, candidate)


def discord_id_from(membership):
    """Pull the buyer's Discord ID from the membership payload."""
    discord = membership.get("discord")
    if isinstance(discord, dict) and discord.get("id"):
        return discord["id"]
    meta = membership.get("metadata") or {}
    return meta.get("discord_id") or meta.get("discord")


def tier_from(membership):
    """Map the membership's Whop plan/product to a configured tier."""
    for key in (membership.get("plan"), membership.get("product"),
                membership.get("plan_id"), membership.get("product_id")):
        if key and key in config.WHOP_PLAN_TIERS:
            return config.WHOP_PLAN_TIERS[key][0]
    return None


@app.post("/whop/webhook")
def whop_webhook():
    raw = request.get_data()
    if not verify_signature(raw, request.headers.get(WHOP_SIGNATURE_HEADER, "")):
        abort(401, "Invalid Whop signature")

    event = request.get_json(silent=True) or {}
    action = event.get("action") or event.get("type") or ""
    membership = event.get("data") or {}

    discord_id = discord_id_from(membership)
    if not discord_id:
        # Buyer hasn't linked Discord — log so staff can grant manually.
        print(f"[whop] {action}: no Discord ID on membership "
              f"{membership.get('id')} (email={membership.get('email')})")
        return "", 200

    if action in ("membership.went_valid", "membership.experience_claimed",
                  "payment.succeeded"):
        tier = tier_from(membership)
        if tier:
            grant(discord_id, tier)
        else:
            print(f"[whop] {action}: unmapped plan "
                  f"{membership.get('plan') or membership.get('product')}")
    elif action in ("membership.went_invalid", "membership.cancelled",
                    "membership.deleted"):
        revoke(discord_id)
    else:
        print(f"[whop] ignored event: {action}")

    return "", 200


@app.get("/health")
def health():
    return {"ok": True, "service": f"{config.SERVER_NAME} whop webhook"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
