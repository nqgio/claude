"""Environment / secrets loading.

Secrets (eBay keys, OAuth refresh tokens, optional Anthropic key) live in the
project-root `.env` file. Everything else (behavior settings) lives in the
database and is edited from the dashboard.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv, set_key

APP_VERSION = "1.19"  # shown at the bottom of the dashboard sidebar

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
ENV_FILE = Path(os.environ.get("APP_ENV_FILE", PROJECT_DIR / ".env"))
DATA_DIR = Path(os.environ.get("APP_DATA_DIR", PROJECT_DIR / "data"))
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"

load_dotenv(ENV_FILE, override=False)
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_URL = os.environ.get("APP_DB_URL", f"sqlite:///{DATA_DIR / 'app.db'}")
HOST = os.environ.get("APP_HOST", "127.0.0.1")
PORT = int(os.environ.get("APP_PORT", "8000"))
# Separate, public-safe listener that only serves eBay's account-deletion webhook.
NOTIFY_PORT = int(os.environ.get("APP_NOTIFY_PORT", "8001"))
# Logged-out profile used only for browsing products (search, product pages, price checks).
AMAZON_BROWSE_DIR = Path(os.environ.get("AMAZON_BROWSE_DIR", DATA_DIR / "amazon_browse"))
# One profile per buying account lives under here.
AMAZON_ACCOUNTS_DIR = DATA_DIR / "amazon_accounts"
# Single login profile from earlier versions; becomes "Amazon account 1" on upgrade.
LEGACY_AMAZON_PROFILE_DIR = DATA_DIR / "amazon_profile"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def ebay_prefix(environment: str) -> str:
    return "EBAY_SANDBOX_" if environment == "sandbox" else "EBAY_PROD_"


def ebay_keys(environment: str) -> dict:
    p = ebay_prefix(environment)
    return {
        "app_id": env(p + "APP_ID"),
        "dev_id": env(p + "DEV_ID"),
        "cert_id": env(p + "CERT_ID"),
        "runame": env(p + "RUNAME"),
        "refresh_token": env(p + "REFRESH_TOKEN"),
    }


def save_env_value(name: str, value: str) -> None:
    """Persist a value (e.g. a new OAuth refresh token) to .env and the live process."""
    if not ENV_FILE.exists():
        example = PROJECT_DIR / ".env.example"
        ENV_FILE.write_text(example.read_text() if example.exists() else "")
    set_key(str(ENV_FILE), name, value, quote_mode="always")
    os.environ[name] = value


# Keys that can be entered from the dashboard (Settings → API keys). Secret ones are never sent back in full.
EDITABLE_KEYS = {
    "EBAY_SANDBOX_APP_ID": False, "EBAY_SANDBOX_DEV_ID": False, "EBAY_SANDBOX_CERT_ID": True, "EBAY_SANDBOX_RUNAME": False,
    "EBAY_PROD_APP_ID": False, "EBAY_PROD_DEV_ID": False, "EBAY_PROD_CERT_ID": True, "EBAY_PROD_RUNAME": False,
    "EBAY_VERIFICATION_TOKEN": True, "EBAY_DELETION_ENDPOINT_URL": False, "ANTHROPIC_API_KEY": True,
}
