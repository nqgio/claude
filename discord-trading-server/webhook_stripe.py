"""
Optional payment integration: a small Flask endpoint that turns Stripe
checkout / subscription events into Discord tier grants.

This decouples payments from the bot process: Stripe -> this webhook -> writes
the same data/subscriptions.json the bot reads, and the bot's expiry loop /
next role sync applies it. For an instant grant you can also hit the Discord
API here, but the simplest robust pattern is the shared store + a sync.

Flow to wire up:
  1. In your Stripe Checkout, pass the buyer's Discord user id as
     `client_reference_id` (collect it on your sales page / via a Discord OAuth
     "Connect" button) and set price->tier mapping in PRICE_TIERS below.
  2. Deploy this endpoint, add it as a Stripe webhook for the events:
     checkout.session.completed, customer.subscription.deleted.
  3. Set STRIPE_WEBHOOK_SECRET in your .env.

NOTE: This is a reference implementation. Map your real Stripe Price IDs.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, request, abort

try:
    import stripe
except ImportError:  # keep the rest of the repo importable without stripe
    stripe = None

import config

load_dotenv()

STRIPE_SECRET = os.getenv("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
GUILD_ID = os.getenv("GUILD_ID", "0")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
SUBS_FILE = DATA_DIR / "subscriptions.json"

# Map your Stripe Price IDs to tiers and durations (days; None = no expiry).
PRICE_TIERS = {
    "price_premium_monthly": (config.ROLE_PREMIUM, 30),
    "price_elite_monthly":   (config.ROLE_ELITE, 30),
    "price_lifetime":        (config.ROLE_LIFETIME, None),
}

if stripe and STRIPE_SECRET:
    stripe.api_key = STRIPE_SECRET

app = Flask(__name__)


def write_sub(user_id, tier, days):
    subs = json.loads(SUBS_FILE.read_text()) if SUBS_FILE.exists() else {}
    expires = None
    if days:
        expires = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    subs.setdefault(str(GUILD_ID), {})[str(user_id)] = {"tier": tier, "expires": expires}
    SUBS_FILE.write_text(json.dumps(subs, indent=2))


def remove_sub(user_id):
    if not SUBS_FILE.exists():
        return
    subs = json.loads(SUBS_FILE.read_text())
    subs.get(str(GUILD_ID), {}).pop(str(user_id), None)
    SUBS_FILE.write_text(json.dumps(subs, indent=2))


@app.post("/stripe/webhook")
def stripe_webhook():
    if stripe is None:
        abort(500, "stripe library not installed")
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except Exception as exc:  # signature / parse failure
        abort(400, f"Invalid webhook: {exc}")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        discord_id = session.get("client_reference_id")
        # Resolve which price was bought.
        line_items = stripe.checkout.Session.list_line_items(session["id"], limit=1)
        price_id = line_items["data"][0]["price"]["id"] if line_items["data"] else None
        mapping = PRICE_TIERS.get(price_id)
        if discord_id and mapping:
            tier, days = mapping
            write_sub(discord_id, tier, days)
            print(f"Granted {tier} to discord:{discord_id}")

    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        discord_id = (sub.get("metadata") or {}).get("discord_id")
        if discord_id:
            remove_sub(discord_id)
            print(f"Revoked tier for discord:{discord_id}")

    return "", 200


@app.get("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
