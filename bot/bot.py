#!/usr/bin/env python3
"""Shorts Bot: runs all channels on your own computer.

  python3 bot/bot.py setup     install everything (once)
  python3 bot/bot.py           start the dashboard at http://localhost:8765 + the daily scheduler

The dashboard connects each channel's YouTube / Instagram / TikTok, sets posting times, and lets you
run or preview a channel. At each channel's time the bot runs Claude Code headless with the daily
runbook in CLAUDE.md (read comments -> write episode -> render -> post). Secrets live in .env (repo root,
never committed). Logs in bot/logs/, finished videos in channels/<name>/episodes/day-NNN/out/final.mp4.
"""
import datetime as dt
import html
import json
import os
import queue
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path

# Windows: run everything in Python UTF-8 mode (story files contain emoji/curly quotes)
if os.name == "nt" and not sys.flags.utf8_mode:
    os.environ["PYTHONUTF8"] = "1"
    sys.exit(subprocess.call([sys.executable, "-X", "utf8", *sys.argv]))
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

ROOT = Path(__file__).resolve().parent.parent
BOT = ROOT / "bot"
ENV = ROOT / ".env"
CONFIG = BOT / "config.json"
STATE = BOT / "state.json"
LOGS = BOT / "logs"
CLIENT_SECRET = BOT / "client_secret.json"
PORT = int(os.environ.get("BOT_PORT", "8765"))
PY = sys.executable
PY_NAME = "python" if os.name == "nt" else "python3"   # what Claude should type in its shell
YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"]

# ---------------------------------------------------------------- storage
def read_json(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(p, data):
    p.write_text(json.dumps(data, indent=2))


def read_env():
    out = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


ENV_LOCK = threading.Lock()


def set_env(**kv):
    with ENV_LOCK:
        env = read_env()
        env.update({k: v for k, v in kv.items() if v is not None})
        ENV.write_text("".join(f"{k}={v}\n" for k, v in sorted(env.items())))
        try:
            os.chmod(ENV, 0o600)
        except Exception:
            pass


def channels():
    out = []
    order = ["theo", "pickwrong", "modeltown", "lastexit", "inthistown"]
    for cj in sorted((ROOT / "channels").glob("*/channel.json"), key=lambda p: (order.index(p.parent.name) if p.parent.name in order else 99, p.parent.name)):
        c = json.loads(cj.read_text(encoding="utf-8"))
        c["id"] = cj.parent.name
        out.append(c)
    return out


DEFAULT_TIMES = {"theo": "16:31", "pickwrong": "20:07", "modeltown": "12:13", "lastexit": "18:19", "inthistown": "14:23"}


def config():
    cfg = read_json(CONFIG, {})
    cfg.setdefault("channels", {})
    for c in channels():
        cfg["channels"].setdefault(c["id"], {"enabled": False, "time": DEFAULT_TIMES.get(c["id"], "17:07")})
    cfg.setdefault("tiktok_redirect", f"http://localhost:{PORT}/tiktok/callback")
    cfg.setdefault("permission", "safe")  # safe = allow-listed tools; full = --dangerously-skip-permissions
    cfg.setdefault("push", False)
    return cfg


# ---------------------------------------------------------------- checks
def which(cmd):
    return shutil.which(cmd) is not None


def checks():
    def py_has(mod):
        return subprocess.run([PY, "-c", f"import {mod}"], capture_output=True).returncode == 0
    node_pw = subprocess.run(["node", "-e", "require('playwright')"], cwd=ROOT, capture_output=True).returncode == 0 if which("node") else False
    return [
        ("Python packages", all(py_has(m) for m in ("kokoro_onnx", "soundfile", "numpy", "requests", "flask", "google_auth_oauthlib")), "python3 bot/bot.py setup"),
        ("Node.js 18+", which("node"), "Windows: winget install OpenJS.NodeJS.LTS · or nodejs.org"),
        ("Playwright + Chromium", node_pw, "python3 bot/bot.py setup"),
        ("ffmpeg", which("ffmpeg"), "Windows: winget install Gyan.FFmpeg, then reopen this window · macOS: brew install ffmpeg"),
        ("Voice model", (ROOT / "models/kokoro-v1.0.onnx").exists() and (ROOT / "models/voices-v1.0.bin").exists(), "python3 bot/bot.py setup"),
        ("Claude Code CLI", which("claude"), "npm install -g @anthropic-ai/claude-code, then run `claude` once to log in"),
    ] + ([("Git for Windows (Claude Code needs it)", which("git") and which("bash"), "winget install Git.Git, then reopen this window")] if os.name == "nt" else [])


def setup():
    print("Installing Python packages...")
    subprocess.run([PY, "-m", "pip", "install", "-r", str(BOT / "requirements.txt")], check=True)
    if which("npm"):
        print("Installing Playwright (browser renderer)...")
        subprocess.run(["npm", "install", "--no-audit", "--no-fund"], cwd=ROOT, check=True, shell=os.name == "nt")
        subprocess.run(["npx", "playwright", "install", "chromium"], cwd=ROOT, check=True, shell=os.name == "nt")
    else:
        print("!! Node.js not found: install it from nodejs.org, then run setup again.")
    import urllib.request
    (ROOT / "models").mkdir(exist_ok=True)
    base = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
    for f in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
        dest = ROOT / "models" / f
        if not dest.exists() or dest.stat().st_size < 1_000_000:
            print(f"Downloading voice model {f} (one time, ~{'325' if f.endswith('onnx') else '28'} MB)...")
            urllib.request.urlretrieve(base + f, dest)
    print()
    for name, ok, hint in checks():
        print(("  ✅ " if ok else "  ❌ ") + name + ("" if ok else f"   → {hint}"))
    print(f"\nDone. Start the bot with:  {Path(PY).name} bot/bot.py")


# ---------------------------------------------------------------- jobs
JOBS = queue.Queue()
RUNNING = {"job": None}
STATE_LOCK = threading.Lock()

SAFE_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep",
              "Bash(python3:*)", "Bash(python:*)", "Bash(node:*)", "Bash(ffmpeg:*)", "Bash(ffprobe:*)",
              "Bash(git add:*)", "Bash(git commit:*)", "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git push:*)",
              "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(mkdir:*)", "Bash(cp:*)"]


def job_prompt(ch, mode, report):
    common = (f"You are running unattended from the local Shorts Bot on the user's computer. Channel: `{ch}` (folder channels/{ch}). "
              f"Read CLAUDE.md and channels/{ch}/bible.json first. Use `{PY_NAME}` for Python (this computer is {'Windows' if os.name == 'nt' else 'Mac/Linux'}). Skip `bash scripts/bootstrap.sh` (the bot already set up this machine). "
              f"Do not use SendUserFile or ask questions; nobody is watching. If something fails, fix it if you can, otherwise stop. ")
    git = "Commit the channel's story.json and episode json files locally" + (" and push." if config()["push"] else "; do NOT push.")
    if mode == "preview":
        task = ("Do runbook steps 2-6 only: fetch comments (if the channel has published episodes), write the next episode.json if it doesn't exist, "
                "preview, fix, and render the final video. Do NOT publish and do NOT change story.json. ")
    else:
        task = (f"Do the full DAILY RUNBOOK (steps 1-8 and 10) for this channel, today. Step 1: run `{PY_NAME} scripts/check_setup.py`; if this channel has no platform connected, stop. "
                f"If today's episode was already published (its published.json has entries), stop. {git} ")
    return common + task + f"Finish by writing your 3-5 line report (plain text) to {report}."


def run_job(ch, mode):
    LOGS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    log = LOGS / f"{ch}_{mode}_{stamp}.log"
    report = LOGS / f"{ch}_{mode}_{stamp}.report.txt"
    cfg = config()
    claude = shutil.which("claude") or "claude"   # on Windows this finds claude.cmd / claude.exe
    cmd = [claude, "-p", job_prompt(ch, mode, report), "--output-format", "text"]
    if cfg["permission"] == "full":
        cmd.append("--dangerously-skip-permissions")
    else:
        cmd += ["--permission-mode", "acceptEdits", "--allowedTools", *SAFE_TOOLS]
    env = dict(os.environ, **read_env(), BOT_MODE="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    update_state(ch, status="running", mode=mode, started=stamp, log=log.name, report=None)
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as fh:
        fh.write(f"$ claude -p <runbook prompt for {ch}, mode={mode}>\n\n"); fh.flush()
        try:
            rc = subprocess.run(cmd, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT, timeout=3 * 3600, shell=False).returncode
        except FileNotFoundError:
            fh.write("Claude Code CLI not found. Install it: npm install -g @anthropic-ai/claude-code\n"); rc = 127
        except subprocess.TimeoutExpired:
            fh.write("\nTimed out after 3 hours.\n"); rc = 124
    rep = report.read_text(encoding="utf-8", errors="replace") if report.exists() else ""
    update_state(ch, status="ok" if rc == 0 else f"failed ({rc})", minutes=round((time.time() - t0) / 60, 1),
                 report=rep.strip()[:2000], finished=dt.datetime.now().strftime("%Y-%m-%d %H:%M"))


def update_state(ch, **kv):
    with STATE_LOCK:
        st = read_json(STATE, {})
        st.setdefault(ch, {}).update(kv)
        write_json(STATE, st)


def worker():
    while True:
        ch, mode = JOBS.get()
        RUNNING["job"] = (ch, mode)
        try:
            run_job(ch, mode)
        except Exception as e:
            update_state(ch, status=f"error: {e}")
        RUNNING["job"] = None


def scheduler():
    while True:
        try:
            cfg = config()
            now = dt.datetime.now()
            today = now.strftime("%Y-%m-%d")
            for ch, c in cfg["channels"].items():
                if not c.get("enabled") or c.get("last_auto") == today:
                    continue
                if now.strftime("%H:%M") >= c.get("time", "23:59"):
                    c["last_auto"] = today
                    write_json(CONFIG, cfg)
                    JOBS.put((ch, "daily"))
            refresh_instagram_tokens(cfg)
        except Exception as e:
            print("scheduler:", e)
        time.sleep(30)


def refresh_instagram_tokens(cfg):
    """Instagram long-lived tokens expire after 60 days; refresh each one every ~45 days automatically."""
    import requests
    env = read_env()
    for c in channels():
        p = c["env_prefix"]
        tok = env.get(f"{p}_IG_ACCESS_TOKEN")
        saved = cfg.get("ig_saved", {}).get(c["id"])
        if not tok or not saved or (dt.date.today() - dt.date.fromisoformat(saved)).days < 45:
            continue
        r = requests.get("https://graph.instagram.com/refresh_access_token", params={"grant_type": "ig_refresh_token", "access_token": tok}, timeout=30)
        if r.ok and "access_token" in r.json():
            set_env(**{f"{p}_IG_ACCESS_TOKEN": r.json()["access_token"]})
            cfg.setdefault("ig_saved", {})[c["id"]] = dt.date.today().isoformat()
            write_json(CONFIG, cfg)


# ---------------------------------------------------------------- web app
from flask import Flask, redirect, request, send_file, abort  # noqa: E402

app = Flask(__name__)
FLASH = {"msg": ""}
OAUTH = {}  # state -> channel id


def connected(c, env):
    p = c["env_prefix"]
    return {
        "youtube": bool(env.get(f"{p}_YT_REFRESH_TOKEN")),
        "instagram": bool(env.get(f"{p}_IG_ACCESS_TOKEN") and env.get(f"{p}_IG_USER_ID")),
        "tiktok": bool(env.get(f"{p}_TIKTOK_REFRESH_TOKEN")),
    }


CSS = """
:root{--bg:#0f1117;--card:#181b24;--line:#2a2f3c;--text:#e9ebf1;--mute:#9aa1b2;--ok:#3ecf8e;--bad:#ff6b6b;--acc:#ffd23f;--blue:#5b8cff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:28px 18px 80px}h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 10px}
.mute{color:var(--mute)}.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin:10px 0}
.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.grow{flex:1}
.chip{display:inline-block;padding:3px 10px;border-radius:99px;font-size:13px;border:1px solid var(--line)}
.ok{color:var(--ok);border-color:#24533f}.bad{color:var(--bad);border-color:#5a2a2a}.run{color:var(--acc);border-color:#5a4a1a}
button,.btn{background:#262b38;color:var(--text);border:1px solid var(--line);border-radius:9px;padding:7px 12px;font:inherit;cursor:pointer;text-decoration:none;display:inline-block}
button.primary{background:var(--blue);border-color:var(--blue);color:#fff}input,select{background:#0f1117;color:var(--text);border:1px solid var(--line);border-radius:8px;padding:7px 9px;font:inherit}
img.av{width:56px;height:56px;border-radius:50%}details{margin-top:10px}summary{cursor:pointer;color:var(--mute)}
pre{white-space:pre-wrap;background:#0b0d12;border:1px solid var(--line);border-radius:10px;padding:12px;max-height:70vh;overflow:auto;font-size:13px}
.flash{background:#1d2a1f;border:1px solid #2f5a3a;padding:10px 14px;border-radius:10px;margin:12px 0}
form.inline{display:inline-flex;gap:6px;align-items:center;flex-wrap:wrap}
"""


def page(body, refresh=False):
    msg = FLASH.pop("msg", "") if FLASH.get("msg") else ""
    FLASH["msg"] = ""
    return (f"<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>Shorts Bot</title><style>{CSS}</style>{'<meta http-equiv=refresh content=20>' if refresh else ''}</head><body><main>"
            f"{'<div class=flash>' + msg + '</div>' if msg else ''}{body}</main></body></html>")


def flash(msg):
    FLASH["msg"] = msg


@app.get("/")
def home():
    cfg, env, st = config(), read_env(), read_json(STATE, {})
    chk = checks()
    h = "<h1>Shorts Bot</h1><div class=mute>Runs your channels from this computer. Keep this window open (and the computer awake) at posting times.</div>"
    bad = [c for c in chk if not c[1]]
    h += "<h2>1 · This computer</h2><div class=card>" + "".join(
        f"<div class=row><span class='chip {'ok' if ok else 'bad'}'>{'✓' if ok else '✗'}</span><span class=grow>{n}</span>{'' if ok else '<span class=mute>' + html.escape(hint) + '</span>'}</div>"
        for n, ok, hint in chk) + ("" if not bad else "<p class=mute>Fix the ✗ items, then refresh.</p>") + "</div>"

    yt_ok = CLIENT_SECRET.exists()
    tt_ok = bool(env.get("TIKTOK_CLIENT_KEY") and env.get("TIKTOK_CLIENT_SECRET"))
    h += f"""<h2>2 · App keys (once, shared by all channels)</h2><div class=card>
      <div class=row><span class='chip {"ok" if yt_ok else "bad"}'>Google / YouTube</span><span class=grow class=mute>OAuth client JSON (Desktop app) from Google Cloud: see SETUP.md step 2.</span>
      <form class=inline method=post action=/app/youtube enctype=multipart/form-data><input type=file name=f accept=.json required><button>Upload</button></form></div>
      <div class=row style='margin-top:10px'><span class='chip {"ok" if tt_ok else "bad"}'>TikTok (optional)</span><span class=grow></span>
      <form class=inline method=post action=/app/tiktok><input name=key placeholder='client key' value='{html.escape(env.get("TIKTOK_CLIENT_KEY", ""))}'>
      <input name=secret placeholder='client secret' type=password><input name=redirect size=34 value='{html.escape(cfg["tiktok_redirect"])}' title='Redirect URI registered in your TikTok app'><button>Save</button></form></div>
      <p class=mute>Instagram needs no app key here: you paste a token per account below.</p></div>"""

    h += "<h2>3 · Channels</h2>"
    for c in channels():
        cid, p = c["id"], c["env_prefix"]
        cc, s = cfg["channels"][cid], st.get(cid, {})
        con = connected(c, env)
        av = f"/brand/{cid}" if (ROOT / f"assets/brand/{cid}/avatar.png").exists() else ""
        running = RUNNING["job"] and RUNNING["job"][0] == cid
        queued = any(j[0] == cid for j in list(JOBS.queue))
        status = "running…" if running else "queued" if queued else s.get("status", "never run")
        cls = "run" if running or queued else "ok" if status == "ok" else "bad" if status.startswith(("fail", "error")) else ""
        last_video = latest_video(cid)
        h += f"""<div class=card><div class=row>{f'<img class=av src={av}>' if av else ''}<div class=grow><b>{html.escape(c['name'])}</b>
          <div class=mute>{cid} · keys prefixed {p}_</div></div>
          {''.join(f"<span class='chip {'ok' if v else ''}'>{k} {'✓' if v else '–'}</span>" for k, v in con.items())}</div>
          <div class=row style='margin-top:12px'>
            <form class=inline method=post action=/schedule/{cid}><label><input type=checkbox name=enabled {'checked' if cc.get('enabled') else ''}> post daily at</label>
              <input type=time name=time value='{cc.get('time')}'><button>Save</button></form><span class=grow></span>
            <form class=inline method=post action=/run/{cid}/preview><button title='Write + render the next video, no posting'>Make video only</button></form>
            <form class=inline method=post action=/run/{cid}/daily><button class=primary title='Full daily run: comments, episode, render, post'>Run now</button></form></div>
          <div class=row style='margin-top:10px'><span class='chip {cls}'>{html.escape(status)}</span>
            <span class=mute>{html.escape(s.get('finished', s.get('started', '')) or '')}</span>
            {f"<a class=btn href='/log/{s['log']}'>log</a>" if s.get('log') else ''}
            {f"<a class=btn href='/video/{cid}'>latest video ({last_video.parent.parent.name})</a>" if last_video else ''}</div>
          {f"<pre>{html.escape(s['report'])}</pre>" if s.get('report') else ''}
          <details><summary>Connect accounts</summary><div style='margin-top:10px'>
            <div class=row><b style='width:90px'>YouTube</b><span class=grow class=mute>Opens Google sign-in. Pick the account / brand channel for <b>{html.escape(c['name'])}</b>.</span>
              <form class=inline method=post action=/connect/youtube/{cid}><button {'disabled' if not yt_ok else ''}>{'Reconnect' if con['youtube'] else 'Connect'}</button></form></div>
            <div class=row style='margin-top:8px'><b style='width:90px'>Instagram</b>
              <form class=inline method=post action=/connect/instagram/{cid}><input name=uid placeholder='Instagram user ID' value='{html.escape(env.get(p + "_IG_USER_ID", ""))}'>
              <input name=tok placeholder='long-lived access token' type=password><button>Save</button></form>
              <span class=mute>From developers.facebook.com → your app → Instagram → Generate token (SETUP.md step 3). Refreshed automatically.</span></div>
            <div class=row style='margin-top:8px'><b style='width:90px'>TikTok</b><span class=grow class=mute>Videos go to your TikTok drafts until your app is approved for direct posting.</span>
              <a class=btn href='/connect/tiktok/{cid}'>{'Reconnect' if con['tiktok'] else 'Connect'}</a></div>
            <div class=row style='margin-top:8px'><b style='width:90px'>Test</b><form class=inline method=post action=/test/{cid}><button>Check logins</button></form></div>
          </div></details></div>"""

    h += f"""<h2>4 · Settings</h2><div class=card><form class=inline method=post action=/settings>
      <label>Claude permissions <select name=permission><option value=safe {'selected' if cfg['permission']=='safe' else ''}>Safe: only the tools the runbook needs</option>
      <option value=full {'selected' if cfg['permission']=='full' else ''}>Full: skip all permission checks</option></select></label>
      <label><input type=checkbox name=push {'checked' if cfg['push'] else ''}> push story commits to GitHub</label><button>Save</button></form>
      <p class=mute>Each run uses your Claude plan (Claude Code). Renders take ~2 min (2D) or ~10 min (3D). Jobs run one at a time.</p></div>"""
    return page(h, refresh=True)


def latest_video(cid):
    vids = sorted((ROOT / "channels" / cid / "episodes").glob("day-*/out/final.mp4"))
    return vids[-1] if vids else None


@app.get("/brand/<cid>")
def brand(cid):
    f = ROOT / "assets/brand" / cid / "avatar.png"
    return send_file(f) if f.exists() and cid in [c["id"] for c in channels()] else abort(404)


@app.get("/video/<cid>")
def video(cid):
    if cid not in [c["id"] for c in channels()]:
        abort(404)
    v = latest_video(cid)
    return send_file(v) if v else abort(404)


@app.get("/log/<name>")
def log(name):
    f = (LOGS / name).resolve()
    if f.parent != LOGS.resolve() or not f.exists():
        abort(404)
    return page(f"<a class=btn href=/>← back</a><h2>{html.escape(name)}</h2><pre>{html.escape(f.read_text(encoding="utf-8", errors="replace")[-200000:])}</pre>")


@app.post("/run/<cid>/<mode>")
def run(cid, mode):
    if cid in [c["id"] for c in channels()] and mode in ("daily", "preview"):
        JOBS.put((cid, mode))
        flash(f"Queued {mode} run for {cid}.")
    return redirect("/")


@app.post("/schedule/<cid>")
def schedule(cid):
    cfg = config()
    if cid in cfg["channels"]:
        c = cfg["channels"][cid]
        was_on = c.get("enabled")
        c.update(enabled=bool(request.form.get("enabled")), time=request.form.get("time", "17:07"))
        now = dt.datetime.now()
        if c["enabled"] and not was_on and now.strftime("%H:%M") >= c["time"]:
            c["last_auto"] = now.strftime("%Y-%m-%d")  # just switched on after today's time: start tomorrow
        write_json(CONFIG, cfg)
        flash(f"Saved schedule for {cid}.")
    return redirect("/")


@app.post("/settings")
def settings():
    cfg = config()
    cfg["permission"] = request.form.get("permission", "safe")
    cfg["push"] = bool(request.form.get("push"))
    write_json(CONFIG, cfg)
    flash("Settings saved.")
    return redirect("/")


@app.post("/app/youtube")
def app_youtube():
    f = request.files.get("f")
    data = json.loads(f.read())
    cfgd = data.get("installed") or data.get("web")
    if not cfgd:
        flash("That file isn't a Google OAuth client JSON. Create a Desktop app OAuth client in Google Cloud.")
        return redirect("/")
    CLIENT_SECRET.write_text(json.dumps(data))
    set_env(YT_CLIENT_ID=cfgd["client_id"], YT_CLIENT_SECRET=cfgd["client_secret"])
    flash("Google app saved. Now connect YouTube for each channel.")
    return redirect("/")


@app.post("/app/tiktok")
def app_tiktok():
    kv = {"TIKTOK_CLIENT_KEY": request.form.get("key") or None, "TIKTOK_CLIENT_SECRET": request.form.get("secret") or None}
    set_env(**kv)
    cfg = config()
    cfg["tiktok_redirect"] = request.form.get("redirect") or cfg["tiktok_redirect"]
    write_json(CONFIG, cfg)
    flash("TikTok app saved.")
    return redirect("/")


@app.post("/connect/youtube/<cid>")
def connect_youtube(cid):
    c = next(c for c in channels() if c["id"] == cid)

    def go():
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), YT_SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True, access_type="offline", prompt="consent select_account",
                                      success_message=f"YouTube connected for {c['name']}. You can close this tab.")
        set_env(**{f"{c['env_prefix']}_YT_REFRESH_TOKEN": creds.refresh_token})
        flash(f"YouTube connected for {c['name']}.")
    threading.Thread(target=go, daemon=True).start()
    flash(f"A Google sign-in tab is opening. Choose the account/channel for {c['name']}, then come back and refresh.")
    return redirect("/")


@app.post("/connect/instagram/<cid>")
def connect_instagram(cid):
    c = next(c for c in channels() if c["id"] == cid)
    uid, tok = request.form.get("uid", "").strip(), request.form.get("tok", "").strip()
    kv = {f"{c['env_prefix']}_IG_USER_ID": uid or None, f"{c['env_prefix']}_IG_ACCESS_TOKEN": tok or None}
    set_env(**kv)
    if tok:
        cfg = config(); cfg.setdefault("ig_saved", {})[cid] = dt.date.today().isoformat(); write_json(CONFIG, cfg)
    flash(f"Instagram saved for {c['name']}. Use 'Check logins' to test it.")
    return redirect("/")


@app.get("/connect/tiktok/<cid>")
def connect_tiktok(cid):
    env, cfg = read_env(), config()
    if not env.get("TIKTOK_CLIENT_KEY"):
        flash("Add your TikTok app's client key and secret in step 2 first.")
        return redirect("/")
    state = secrets.token_urlsafe(12)
    OAUTH[state] = cid
    url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode({
        "client_key": env["TIKTOK_CLIENT_KEY"], "scope": "user.info.basic,video.upload,video.publish",
        "response_type": "code", "redirect_uri": cfg["tiktok_redirect"], "state": state})
    local = cfg["tiktok_redirect"].startswith(f"http://localhost:{PORT}")
    return page(f"""<a class=btn href=/>← back</a><h2>Connect TikTok for {html.escape(cid)}</h2><div class=card>
      <p>1. <a class=btn href='{html.escape(url)}' target=_blank>Open TikTok sign-in</a> and approve with the account for this channel.</p>
      {'<p>2. You will come back here automatically.</p>' if local else f'''<p>2. TikTok sends you to <code>{html.escape(cfg["tiktok_redirect"])}</code>. Copy that whole address from the browser bar and paste it here:</p>
      <form method=post action=/tiktok/paste><input type=hidden name=state value='{state}'><input name=url size=70 placeholder='https://...?code=...&state=...'><button class=primary>Connect</button></form>'''}
      </div>""")


def tiktok_exchange(code, state):
    import requests
    cid = OAUTH.pop(state, None)
    if not cid:
        return "This sign-in link expired. Start again from the dashboard."
    env, cfg = read_env(), config()
    c = next(c for c in channels() if c["id"] == cid)
    r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", headers={"Content-Type": "application/x-www-form-urlencoded"}, data={
        "client_key": env["TIKTOK_CLIENT_KEY"], "client_secret": env["TIKTOK_CLIENT_SECRET"], "code": code,
        "grant_type": "authorization_code", "redirect_uri": cfg["tiktok_redirect"]}, timeout=30).json()
    if "refresh_token" not in r:
        return f"TikTok said: {r}"
    set_env(**{f"{c['env_prefix']}_TIKTOK_REFRESH_TOKEN": r["refresh_token"]})
    return f"TikTok connected for {c['name']}."


@app.get("/tiktok/callback")
def tiktok_callback():
    flash(tiktok_exchange(request.args.get("code", ""), request.args.get("state", "")))
    return redirect("/")


@app.post("/tiktok/paste")
def tiktok_paste():
    q = urllib.parse.parse_qs(urllib.parse.urlparse(request.form.get("url", "")).query)
    flash(tiktok_exchange((q.get("code") or [""])[0], request.form.get("state", "")))
    return redirect("/")


@app.post("/test/<cid>")
def test(cid):
    c = next(c for c in channels() if c["id"] == cid)
    code = ("import sys; sys.path.insert(0,'scripts'); import channel as ch, json\n"
            f"cfg=ch.load(ch.channel_dir('{cid}'))['channel']; ch.use_credentials(cfg)\n"
            "from platforms import youtube, instagram, tiktok\nfrom platforms.common import req\n"
            "for m,t in [(youtube,lambda: youtube.my_channel_id()),(instagram,lambda: req('GET', instagram.API+'/me?fields=username&access_token='+instagram._e()['IG_ACCESS_TOKEN']).json()['username']),(tiktok,lambda: tiktok._token() and 'ok')]:\n"
            "  if not m.configured(): print(m.NAME+': not connected'); continue\n"
            "  try: print(m.NAME+': OK ('+str(t())+')')\n"
            "  except Exception as e: print(m.NAME+': FAILED '+str(e)[:200])\n")
    r = subprocess.run([PY, "-c", code], cwd=ROOT, env=dict(os.environ, **read_env()), capture_output=True, text=True, timeout=120)
    flash(f"<b>{html.escape(c['name'])}</b><br>" + "<br>".join(html.escape(l) for l in (r.stdout + r.stderr).strip().splitlines()[-6:]))
    return redirect("/")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        return setup()
    LOGS.mkdir(parents=True, exist_ok=True)
    write_json(CONFIG, config())
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=scheduler, daemon=True).start()
    url = f"http://localhost:{PORT}"
    print(f"\n  Shorts Bot is running → {url}\n  Keep this window open. Ctrl+C to stop.\n")
    try:
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    except Exception:
        pass
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
