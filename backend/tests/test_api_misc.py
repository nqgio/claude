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
    assert b["ebay_price"] == 22.99 and b["profit"] == 3.23


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


def test_api_keys_saved_to_env_file(api, monkeypatch):
    import os

    from app import config

    for k in config.EDITABLE_KEYS:
        monkeypatch.setenv(k, "")  # registers the original so values saved below are undone after the test
        monkeypatch.delenv(k)
    if config.ENV_FILE.exists():
        config.ENV_FILE.unlink()
    r = api.put("/api/keys", json={"EBAY_SANDBOX_APP_ID": "  MyApp-SBX-123 ", "EBAY_SANDBOX_CERT_ID": "SBX-secret-abcd1234",
                                  "EBAY_SANDBOX_RUNAME": ""})
    assert r.status_code == 200 and set(r.json()["changed"]) == {"EBAY_SANDBOX_APP_ID", "EBAY_SANDBOX_CERT_ID"}
    keys = r.json()["keys"]
    assert keys["EBAY_SANDBOX_APP_ID"]["display"] == "MyApp-SBX-123"
    assert keys["EBAY_SANDBOX_CERT_ID"]["display"].endswith("1234") and "secret" not in keys["EBAY_SANDBOX_CERT_ID"]["display"]
    assert not keys["EBAY_SANDBOX_RUNAME"]["set"]
    text = config.ENV_FILE.read_text()
    assert "EBAY_SANDBOX_APP_ID='MyApp-SBX-123'" in text and "EBAY_PROD_APP_ID" in text  # created from .env.example
    assert os.environ["EBAY_SANDBOX_CERT_ID"] == "SBX-secret-abcd1234"  # live without restart
    s = api.get("/api/status").json()["ebay"]
    assert s["keys_present"] and not s["runame_present"]
    # blank never wipes; bad values rejected
    api.put("/api/keys", json={"EBAY_SANDBOX_APP_ID": ""})
    assert os.environ["EBAY_SANDBOX_APP_ID"] == "MyApp-SBX-123"
    assert api.put("/api/keys", json={"EBAY_VERIFICATION_TOKEN": "short"}).status_code == 400
    assert api.put("/api/keys", json={"NOT_A_KEY": "x"}).status_code == 400


def test_block_remembers_page_and_solve_endpoint(api, monkeypatch):
    from app.providers import amazon_playwright as ap
    from app.providers import get_provider

    ap.pause_for_block("robot check page", "https://www.amazon.com/dp/B0TEST0001")
    assert st.get("amazon_blocked_url").endswith("B0TEST0001") and api.get("/api/status").json()["amazon"]["status"] == "paused"
    st.update({"product_source": "sample"})
    assert api.post("/api/amazon/solve").status_code == 400  # only for the Amazon source
    st.update({"product_source": "amazon_playwright"})
    opened = []
    monkeypatch.setattr(get_provider("amazon_playwright"), "open_solve_browser", lambda: opened.append(1) or "opened")
    assert "window opened" in api.post("/api/amazon/solve").json()["message"]
    assert opened
    ap.resume("test")
    assert st.get("amazon_paused_until") is None and st.get("amazon_blocked_url") == ""


def test_queue_build_progress(sample_source):
    from app.services import queue

    st.update({"posting_window_start": "00:00", "posting_window_end": "23:59", "listings_per_day": 2})
    res = queue.build_queue("test")
    p = queue.PROGRESS
    assert not p["running"] and p["target"] == 4 and p["added"] == res["added"] == 4
    assert p["examined"] >= 4 and p["result"].startswith("Done") and p["finished_at"]
    st.update({"search_keywords": []})
    queue.build_queue("test")
    assert "No search keywords" in queue.PROGRESS["result"] and not queue.PROGRESS["running"]


def test_stop_search_ends_quickly_and_keeps_found_items(sample_source, monkeypatch):
    import threading
    import time

    from app.db import session_scope
    from app.models import QueueItem
    from app.providers import amazon_playwright as ap
    from app.providers import get_provider
    from app.services import queue

    st.update({"posting_window_start": "00:00", "posting_window_end": "23:59", "listings_per_day": 5})
    prov = get_provider()
    real_get = prov.get_product

    def slow_get(asin):  # behaves like the paced Amazon source: waits between pages
        ap._sleep(5)
        return real_get(asin)

    monkeypatch.setattr(prov, "get_product", slow_get)
    t = threading.Thread(target=queue.build_queue, args=("test",))
    started = time.monotonic()
    t.start()
    time.sleep(0.3)
    assert queue.PROGRESS["running"]
    assert queue.stop_build()
    t.join(timeout=10)
    assert not t.is_alive() and time.monotonic() - started < 3  # didn't wait out the 5 s pause
    assert queue.PROGRESS["result"].startswith("Stopped by you") and not queue.PROGRESS["running"]
    assert not queue.stop_build()  # nothing running any more
    from app.providers.base import STOP_EVENT

    assert not STOP_EVENT.is_set()  # cleared, so the next build runs normally
    monkeypatch.setattr(prov, "get_product", real_get)
    queue.build_queue("test")
    with session_scope() as s:
        assert s.query(QueueItem).count() >= 1
    assert queue.PROGRESS["result"].startswith("Done")


def test_progress_panel_explains_amazon_waits(sample_source, monkeypatch):
    """The hourly page limit / a busy browser show in the build progress instead of looking frozen."""
    import threading
    import time

    from app.providers import amazon_playwright as ap
    from app.services import queue

    st.update({"amazon_max_pages_per_hour": 1, "amazon_min_delay_sec": 1, "amazon_max_delay_sec": 1,
               "posting_window_start": "00:00", "posting_window_end": "23:59"})
    pacer = ap._Pacer()
    pacer.recent.append(time.monotonic())  # one page already read this hour → budget used up
    prov = queue.get_provider()
    real = prov.get_product
    monkeypatch.setattr(prov, "get_product", lambda asin: (pacer.wait(), real(asin))[1])
    t = threading.Thread(target=queue.build_queue, args=("test",))
    t.start()
    for _ in range(50):
        time.sleep(0.1)
        if queue.PROGRESS.get("waiting"):
            break
    assert queue.PROGRESS["waiting"] and "pages/hour limit" in queue.PROGRESS["step"]
    queue.stop_build()
    t.join(timeout=10)
    assert not t.is_alive() and not queue.PROGRESS["running"]
