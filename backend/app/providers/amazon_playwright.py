"""Amazon product source using Playwright with a persistent browser profile.

* All browser work runs on ONE dedicated thread (Playwright's sync API is not
  thread-safe); callers block on a future.
* Requests are paced like a person: a random delay between pages plus an hourly
  page budget (both adjustable in Settings).
* If Amazon shows a CAPTCHA / robot check we do NOT try to get past it: Amazon
  jobs pause for the configured cooldown, the event is logged and the dashboard
  shows an alert.
* The profile directory keeps your Amazon login (you log in manually once via
  Settings → "Open Amazon browser"). Your password and card are never stored by
  this app.
"""
from __future__ import annotations

import os
import random
import re
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

from .. import activity, config
from .. import settings_store as st
from . import amazon_parser as parser
from .base import (ProductData, ProductProvider, ProviderError, PurchaseResult, SearchResult, SourceBlocked,
                   SourcePaused, TrackingInfo)

BASE = "https://www.amazon.com"


def paused_until() -> datetime | None:
    raw = st.get("amazon_paused_until")
    if not raw:
        return None
    try:
        until = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return until


def check_not_paused() -> None:
    until = paused_until()
    if until is None:
        return
    if datetime.now(timezone.utc) < until:
        raise SourcePaused(f"Amazon jobs paused until {until.isoformat()} ({st.get('amazon_pause_reason')})")
    resume("Amazon cooldown finished — Amazon jobs resumed")


def pause_for_block(reason: str, url: str = "") -> None:
    minutes = int(st.get("amazon_cooldown_minutes"))
    until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    st.set_internal("amazon_paused_until", until.isoformat())
    st.set_internal("amazon_pause_reason", reason)
    st.set_internal("amazon_blocked_url", url)
    activity.warning("amazon", f"Amazon showed a CAPTCHA/block ({reason}). Not bypassing it — all Amazon jobs "
                               f"paused for {minutes} minutes. You can solve it yourself with “Solve it in a browser”.")


def resume(message: str) -> None:
    st.set_internal("amazon_paused_until", None)
    st.set_internal("amazon_pause_reason", "")
    st.set_internal("amazon_blocked_url", "")
    activity.info("amazon", message)


# Cookies Amazon sets only for a signed-in session ("Keep me signed in" makes them persist).
AUTH_COOKIES = {"at-main", "sess-at-main"}


def has_auth_cookie(ctx) -> bool:
    try:
        return any(c.get("name") in AUTH_COOKIES and c.get("value") for c in ctx.cookies(["https://www.amazon.com"]))
    except Exception:
        return False


class _Pacer:
    def __init__(self):
        self.recent: deque[float] = deque()
        self.last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        while self.recent and now - self.recent[0] > 3600:
            self.recent.popleft()
        budget = int(st.get("amazon_max_pages_per_hour"))
        if len(self.recent) >= budget:
            sleep_for = 3600 - (now - self.recent[0]) + random.uniform(1, 10)
            activity.info("amazon", f"Hourly page budget ({budget}) reached — waiting {int(sleep_for // 60)} min")
            time.sleep(max(0.0, sleep_for))
        lo, hi = float(st.get("amazon_min_delay_sec")), float(st.get("amazon_max_delay_sec"))
        gap = random.uniform(lo, max(lo, hi))
        elapsed = time.monotonic() - self.last
        if elapsed < gap:
            time.sleep(gap - elapsed)
        self.last = time.monotonic()
        self.recent.append(self.last)


class AmazonPlaywrightProvider(ProductProvider):
    name = "amazon_playwright"

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="amazon")
        self._pw = None
        self._ctx = None
        self._headless = None
        self._pacer = _Pacer()
        self._lock = threading.Lock()
        self._profile = None  # profile directory of the open browser
        self._want = str(config.AMAZON_BROWSE_DIR)  # profile the current operation needs
        self._solving = False

    # ---- thread plumbing -----------------------------------------------------
    def _run(self, fn, *args, timeout: float | None = None):
        return self._executor.submit(fn, *args).result(timeout=timeout)

    def _use(self, profile: str | None) -> None:
        """Select the browser profile for the next steps: an account's login profile,
        or (default) the logged-out browsing profile."""
        self._want = str(profile or config.AMAZON_BROWSE_DIR)

    def _context(self, headless: bool | None = None):
        want = bool(st.get("amazon_headless")) if headless is None else headless
        if self._ctx is not None and self._headless == want and self._profile == self._want:
            return self._ctx
        self._close_ctx()
        if self._pw is None:
            from playwright.sync_api import sync_playwright

            self._pw = sync_playwright().start()
        os.makedirs(self._want, exist_ok=True)
        kwargs = dict(user_data_dir=self._want, headless=want, locale="en-US",
                      viewport={"width": 1366, "height": 900}, timezone_id=None)
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        exe = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
        if exe:
            kwargs["executable_path"] = exe
        self._ctx = self._pw.chromium.launch_persistent_context(**kwargs)
        self._ctx.set_default_timeout(45000)
        self._headless, self._profile = want, self._want
        return self._ctx

    def _close_ctx(self):
        if self._ctx is not None:
            try:
                self._ctx.close()
            except Exception:
                pass
            self._ctx = None

    def _page(self):
        ctx = self._context()
        return ctx.pages[0] if ctx.pages else ctx.new_page()

    def _goto(self, url: str) -> str:
        check_not_paused()
        self._pacer.wait()
        page = self._page()
        try:
            resp = page.goto(url, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("load", timeout=15000)
            except Exception:
                pass
        except Exception as exc:
            raise ProviderError(f"failed to load {url}: {exc}") from exc
        html = page.content()
        if parser.is_block_page(html, page.url) or (resp is not None and resp.status == 503 and "amazon" in html.lower()):
            pause_for_block("robot check page", page.url)
            raise SourceBlocked("Amazon showed a CAPTCHA / robot check")
        if resp is not None and resp.status == 404:
            raise ProviderError("page not found (404)")
        return html

    # ---- ProductProvider -------------------------------------------------------
    def search(self, term: str, category: str | None, page: int) -> list[SearchResult]:
        return self._run(self._search, term, category, page)

    def _search(self, term, category, page):
        self._use(None)
        url = f"{BASE}/s?k={quote_plus(term)}" if term else f"{BASE}/s?"
        if category:
            if category.startswith("node:"):
                url += f"&rh=n%3A{quote_plus(category[5:])}"
            else:
                url += f"&i={quote_plus(category)}"
        if page > 1:
            url += f"&page={page}"
        return parser.parse_search(self._goto(url))

    def get_product(self, asin: str) -> ProductData:
        return self._run(self._get_product, asin)

    def _get_product(self, asin):
        self._use(None)
        url = f"{BASE}/dp/{asin}"
        html = self._goto(url)
        try:
            return parser.parse_product(html, asin, url)
        except ValueError as exc:
            raise ProviderError(f"{asin}: {exc}") from exc

    # ---- login ---------------------------------------------------------------
    def open_login_browser(self, profile: str | None = None, label: str = "Amazon", on_done=None) -> str:
        """Show the account's browser so the person signs in. When the window closes, `on_done(logged_in)`
        is called with whether Amazon's sign-in cookies are present."""
        def _open():
            self._use(profile)
            ctx = self._context(headless=False)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                page.goto(f"{BASE}/gp/sign-in.html")
            except Exception:
                pass
            activity.info("amazon", f"Opened the login window for {label}. Log in (tick “Keep me signed in”), then close the window.")
            logged = has_auth_cookie(ctx)
            deadline = time.time() + 20 * 60
            while time.time() < deadline:
                try:
                    if not ctx.pages:
                        break
                    logged = has_auth_cookie(ctx)
                    ctx.pages[0].wait_for_timeout(2000)
                except Exception:
                    break
            self._close_ctx()
            if logged:
                activity.info("amazon", f"Login window for {label} closed — {label} is logged in")
            else:
                activity.warning("amazon", f"Login window for {label} closed, but it isn't signed in to Amazon. "
                                           "Click Log in again and finish signing in before closing the window.")
            if on_done:
                on_done(logged)
            return "closed"

        self._executor.submit(_open)
        return "opened"

    def open_solve_browser(self) -> str:
        """Show the app's (logged-out) Amazon browser on screen at the blocked page so a person can
        answer the CAPTCHA. Nothing is solved automatically; jobs resume only if the page that was
        open when the window closed is no longer a CAPTCHA."""
        if self._solving:
            return "already open"
        self._solving = True

        def _solve():
            try:
                self._use(None)
                ctx = self._context(headless=False)
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                try:
                    page.goto(st.get("amazon_blocked_url") or BASE + "/", wait_until="domcontentloaded")
                except Exception:
                    pass
                activity.info("amazon", "Opened Amazon on your screen. Solve the CAPTCHA, wait for the normal Amazon page, "
                                        "then close the window.")
                last_html, last_url = "", ""
                deadline = time.time() + 20 * 60
                while time.time() < deadline:
                    try:
                        if not ctx.pages:
                            break
                        pg = ctx.pages[0]
                        last_html, last_url = pg.content(), pg.url
                        pg.wait_for_timeout(1500)
                    except Exception:
                        break
                self._close_ctx()
                if last_html and not parser.is_block_page(last_html, last_url):
                    resume("CAPTCHA solved in the browser — Amazon jobs resumed")
                else:
                    activity.warning("amazon", "The window closed while Amazon still showed a CAPTCHA, so Amazon jobs stay "
                                               "paused. Try “Solve it in a browser” again, or wait for the cooldown.")
            finally:
                self._solving = False

        self._executor.submit(_solve)
        return "opened"

    def _logged_in(self, html: str) -> bool:
        return not re.search(r"Hello,\s*sign in", html, re.I)

    def check_login(self, profile: str | None = None) -> bool:
        """Logged in = the profile holds Amazon's sign-in cookies. No page is loaded, so this never
        triggers a CAPTCHA and works while Amazon jobs are paused."""
        def _check():
            self._use(profile)
            return has_auth_cookie(self._context())

        return self._run(_check, timeout=10 * 60)

    # ---- order tracking -------------------------------------------------------
    def get_tracking(self, order_id: str, profile: str | None = None) -> TrackingInfo | None:
        return self._run(self._get_tracking, order_id, profile)

    def _get_tracking(self, order_id, profile=None):
        self._use(profile)
        html = self._goto(f"{BASE}/gp/your-account/order-details?orderID={quote_plus(order_id)}")
        page = self._page()
        if "/ap/signin" in page.url:
            raise ProviderError("Amazon profile is not logged in (Settings → Open Amazon browser)")
        info = parser.parse_tracking(html)
        link = page.query_selector("a[href*='progress-tracker'], a[href*='ship-track'], a:has-text('Track package')")
        if link and not info.tracking_number:
            href = link.get_attribute("href") or ""
            html2 = self._goto(href if href.startswith("http") else BASE + href)
            info2 = parser.parse_tracking(html2)
            info2.delivered = info2.delivered or info.delivered
            return info2
        return info

    # ---- automatic checkout --------------------------------------------------------
    def place_order(self, asin: str, quantity: int, address: dict, guard, profile: str | None = None) -> PurchaseResult:
        return self._run(self._place_order, asin, quantity, address, guard, profile, timeout=15 * 60)

    def _shot(self, label: str) -> str:
        path = config.SCREENSHOT_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{label}.png"
        try:
            self._page().screenshot(path=str(path), full_page=True)
        except Exception:
            return ""
        return str(path)

    def _click_first(self, page, selectors: list[str], timeout: int = 8000) -> bool:
        for sel in selectors:
            try:
                el = page.wait_for_selector(sel, timeout=timeout, state="visible")
                if el:
                    el.click()
                    return True
            except Exception:
                continue
        return False

    def _place_order(self, asin, quantity, address, guard, profile=None) -> PurchaseResult:
        """Buy Now → ship to the eBay buyer → verify total with `guard` → place order.
        Stops (without ordering) the moment anything looks unexpected."""
        self._use(profile)
        html = self._goto(f"{BASE}/dp/{asin}")
        page = self._page()
        if not self._logged_in(html):
            return PurchaseResult(False, message="Amazon profile is not logged in", screenshot=self._shot("not-logged-in"))
        if quantity > 1:
            try:
                page.select_option("#quantity", str(quantity))
            except Exception:
                return PurchaseResult(False, message="could not set quantity", screenshot=self._shot("qty"))
        if not self._click_first(page, ["#buy-now-button", "input[name='submit.buy-now']"]):
            return PurchaseResult(False, message="Buy Now button not found", screenshot=self._shot("no-buy-now"))
        page.wait_for_load_state("domcontentloaded")
        if "/ap/signin" in page.url:
            return PurchaseResult(False, message="Amazon asked to sign in again", screenshot=self._shot("signin"))

        # Change shipping address to the eBay buyer's address.
        self._click_first(page, ["#addressChangeLinkId", "a[data-args*='shipaddressselectChangeClicked']",
                                 "a:has-text('Change')"], timeout=10000)
        if not self._click_first(page, ["#add-new-address-desktop-sasp-tango-link", "#add-new-address-popover-link",
                                        "a:has-text('Add a new delivery address')", "a:has-text('Add a new address')"]):
            return PurchaseResult(False, message="could not open 'add new address'", screenshot=self._shot("no-add-address"))
        fields = {
            "#address-ui-widgets-enterAddressFullName": address["name"],
            "#address-ui-widgets-enterAddressPhoneNumber": address.get("phone") or "",
            "#address-ui-widgets-enterAddressLine1": address["line1"],
            "#address-ui-widgets-enterAddressLine2": address.get("line2") or "",
            "#address-ui-widgets-enterAddressCity": address["city"],
            "#address-ui-widgets-enterAddressPostalCode": address["postal"],
        }
        try:
            for sel, val in fields.items():
                page.wait_for_selector(sel, timeout=10000)
                page.fill(sel, val)
            page.select_option("#address-ui-widgets-enterAddressStateOrRegion-dropdown-nativeId", address["state"])
        except Exception as exc:
            return PurchaseResult(False, message=f"address form error: {exc}", screenshot=self._shot("address-form"))
        self._click_first(page, ["#address-ui-widgets-form-submit-button input", "#address-ui-widgets-form-submit-button",
                                 "input[aria-labelledby='address-ui-widgets-form-submit-button-announce']"])
        # Amazon may suggest a corrected address; keep the one we entered.
        self._click_first(page, ["input[name='address-ui-widgets-saveOriginalOrSuggestedAddress']",
                                 "#address-ui-widgets-original-address-block_id input"], timeout=4000)
        page.wait_for_timeout(4000)
        review_html = page.content()
        review_text = re.sub(r"\s+", " ", page.inner_text("body"))
        zip5 = address["postal"][:5]
        if zip5 not in review_text or address["name"].split()[0].lower() not in review_text.lower():
            return PurchaseResult(False, message="checkout page does not show the buyer's address — stopped",
                                  screenshot=self._shot("address-mismatch"))
        total = parser.parse_order_total(review_html)
        if total is None:
            return PurchaseResult(False, message="could not read the order total — stopped", screenshot=self._shot("no-total"))
        ok, reason = guard(total, parser.parse_shipping_cost(review_html))
        if not ok:
            return PurchaseResult(False, total_paid=None, message=f"stopped before ordering: {reason}",
                                  screenshot=self._shot("guard-stop"))
        if not self._click_first(page, ["#submitOrderButtonId input", "#placeOrder", "input[name='placeYourOrder1']",
                                        "#bottomSubmitOrderButtonId input"]):
            return PurchaseResult(False, message="Place order button not found", screenshot=self._shot("no-place-order"))
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(5000)
        order_id = parser.parse_order_id(page.content())
        shot = self._shot("order-placed")
        if not order_id:
            return PurchaseResult(True, total_paid=total, message="order placed but order number not found — check Amazon",
                                  screenshot=shot)
        return PurchaseResult(True, order_id=order_id, total_paid=total, message="order placed", screenshot=shot)

    def close(self) -> None:
        def _c():
            self._close_ctx()
            if self._pw is not None:
                self._pw.stop()
                self._pw = None

        try:
            self._run(_c, timeout=30)
        except Exception:
            pass
        self._executor.shutdown(wait=False)
