import hashlib

import pytest
from fastapi.testclient import TestClient

from app import settings_store as st
from app.ebay import client as ebay_client
from app.ebay.notifications import build_app, challenge_response
from app.main import create_app


@pytest.fixture
def api():
    with TestClient(create_app(start_scheduler=False)) as c:
        yield c


def test_settings_roundtrip_and_validation(api):
    r = api.get("/api/settings").json()
    assert r["values"]["dry_run"] is True and r["values"]["sales_tax_percent"] == 6.0
    assert r["values"]["ebay_environment"] == "sandbox"
    assert any(f["key"] == "margin_multiplier" for f in r["schema"])
    ok = api.put("/api/settings", json={"margin_multiplier": "1.35", "min_profit_percent": ""})
    assert ok.status_code == 200 and ok.json()["values"]["margin_multiplier"] == 1.35
    assert ok.json()["values"]["min_profit_percent"] is None
    assert api.put("/api/settings", json={"posting_window_start": "25:00"}).status_code == 400
    assert api.put("/api/settings", json={"rounding_mode": "up"}).status_code == 400
    assert api.put("/api/settings", json={"filter_min_price": 90, "filter_max_price": 50}).status_code == 400
    # hidden internal keys can't be set from the dashboard
    api.put("/api/settings", json={"amazon_paused_until": "2099-01-01T00:00:00+00:00"})
    assert st.get("amazon_paused_until") is None


def test_pricing_preview(api):
    b = api.post("/api/pricing/preview", json={"amazon_price": 13.99}).json()
    assert b["ebay_price"] == 22.99 and b["profit"] == 3.30


def test_blocklist_api(api):
    n = len(api.get("/api/blocklist").json())
    assert n > 50  # seeded on startup
    assert api.post("/api/blocklist", json={"term": "Acme", "kind": "brand"}).json()["added"] == 1
    assert api.post("/api/blocklist/import", json={"csv": "Foo\nbar,keyword\nAcme"}).json()["added"] == 2
    assert len(api.get("/api/blocklist").json()) == n + 3


def test_status_and_activity(api):
    s = api.get("/api/status").json()
    assert s["dry_run"] and s["amazon"]["status"] == "ok" and not s["ebay"]["connected"]
    a = api.get("/api/activity").json()
    assert a["total"] >= 1


def test_oauth_code_extraction():
    code, state = ebay_client.extract_code(
        "https://signin.ebay.com/ws/eBayISAPI.dll?ThirdPartyAuthSucessFailure&isAuthSuccessful=true&state=abc&code=v%5E1.1%23i&expires_in=299")
    assert code == "v^1.1#i" and state == "abc"
    assert ebay_client.extract_code("rawcode")[0] == "rawcode"


def test_account_deletion_challenge(monkeypatch):
    monkeypatch.setenv("EBAY_VERIFICATION_TOKEN", "a" * 40)
    monkeypatch.setenv("EBAY_DELETION_ENDPOINT_URL", "https://example.trycloudflare.com/ebay/account-deletion")
    c = TestClient(build_app())
    r = c.get("/ebay/account-deletion", params={"challenge_code": "xyz"}).json()
    expected = hashlib.sha256(("xyz" + "a" * 40 + "https://example.trycloudflare.com/ebay/account-deletion").encode()).hexdigest()
    assert r["challengeResponse"] == expected == challenge_response("xyz", "a" * 40,
                                                                    "https://example.trycloudflare.com/ebay/account-deletion")
    # unsigned notifications are rejected
    assert c.post("/ebay/account-deletion", content=b"{}").status_code == 412


def test_schedule_spreads_across_window(sample_source):
    from app.db import session_scope
    from app.models import QueueItem, utcnow
    from app.services import queue

    st.update({"posting_window_start": "00:00", "posting_window_end": "23:59", "listings_per_day": 4,
               "queue_backup_factor": 1.5})
    queue.build_queue("test")
    with session_scope() as s:
        times = sorted(q.scheduled_at for q in s.query(QueueItem).filter_by(status="scheduled"))
    assert len(times) == 4
    assert len(set(times)) == 4
    now = utcnow()
    assert all(t > now for t in times)


def test_captcha_pauses_amazon_jobs_then_resumes():
    from datetime import datetime, timedelta, timezone

    from app.providers.amazon_playwright import check_not_paused, pause_for_block
    from app.providers.base import SourcePaused
    from app.services import scheduler

    pause_for_block("test robot check")
    with pytest.raises(SourcePaused):
        check_not_paused()
    scheduler.safe("refresh")()  # a job hitting the pause logs a warning instead of crashing
    # cooldown over → automatically resumes
    st.set_internal("amazon_paused_until", (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    check_not_paused()
    assert st.get("amazon_paused_until") is None
