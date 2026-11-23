import os, time
import requests


def env(*names):
    """Return dict of env vars, or None if any are missing (platform not configured)."""
    vals = {n: os.environ.get(n) for n in names}
    return vals if all(vals.values()) else None


def req(method, url, retries=3, **kw):
    for i in range(retries):
        r = requests.request(method, url, timeout=kw.pop("timeout", 120), **kw)
        if r.status_code < 500 and r.status_code != 429:
            if r.status_code >= 400:
                raise RuntimeError(f"{method} {url.split('?')[0]} -> {r.status_code}: {r.text[:500]}")
            return r
        time.sleep(2 ** (i + 1))
    raise RuntimeError(f"{method} {url.split('?')[0]} failed after retries: {r.status_code} {r.text[:300]}")
