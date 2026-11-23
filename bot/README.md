# Shorts Bot: run every channel from your own computer

A small app that lives on your computer. You connect each channel's accounts in a dashboard,
pick a posting time per channel, and leave it running. Every day at each channel's time it runs
Claude Code (logged in with your Claude account), which follows the daily runbook in `CLAUDE.md`:
reads yesterday's comments → writes the episode → renders the video → posts it → posts the vote comment
→ replies to the winner and cameos.

## 1. Install the basics (once): Windows

Open **PowerShell** (Start menu → type "PowerShell") and paste these one at a time:

```powershell
winget install Python.Python.3.12      # 3.12 has the best support for the voice model
winget install OpenJS.NodeJS.LTS
winget install Gyan.FFmpeg
winget install Git.Git
```

**Close PowerShell and open a new one** (so it sees the new programs), then install Claude Code and log in:

```powershell
npm install -g @anthropic-ai/claude-code
claude
```

`claude` opens a login. Sign in with your Claude account, then type `/exit`.
(Claude Code on Windows needs Git for Windows, which is why it's in the list.)

No winget? Download the installers instead: python.org (tick **"Add python.exe to PATH"**), nodejs.org (LTS),
git-scm.com, and ffmpeg from gyan.dev (add its `bin` folder to PATH).

<details><summary>Mac instead</summary>

`brew install python node ffmpeg`, then `npm install -g @anthropic-ai/claude-code` and run `claude` once to log in.
Start the bot by right-clicking `start-mac.command` → Open.
</details>

## 2. Unzip the project

Unzip `shorts-bot.zip` somewhere permanent, e.g. `Documents\shorts-bot`. Don't run it from inside the zip.

## 3. Start it

Double-click **`start-windows.bat`** (inside the `shorts-bot` folder).
- If Windows says "Windows protected your PC", click **More info → Run anyway** (it's a downloaded file).
- If the firewall asks about Python, click **Allow** (the dashboard only listens on your own computer).
- The first start installs everything (~400 MB including the voice model), then opens **http://localhost:8765**.
- Leave the black window open; closing it stops the bot.

## 4. Connect things in the dashboard

1. **This computer:** everything should be ✓. Anything ✗ shows how to fix it.
2. **App keys (once):**
   - *Google:* follow SETUP.md step 2 (create a Google Cloud project, enable YouTube Data API v3,
     set the consent screen to **In production**, create an OAuth client of type **Desktop app**), download its JSON, and upload it here.
   - *TikTok (optional):* client key + secret from developers.tiktok.com. In your TikTok app, register
     the redirect URI shown in the dashboard (`http://localhost:8765/tiktok/callback`). If TikTok won't accept a localhost
     address, register any https page you own and paste the redirected URL when asked.
3. **Each channel → Connect accounts:**
   - *YouTube:* click **Connect**, sign in, and pick that channel's account / brand channel.
   - *Instagram:* paste the account's user ID + long-lived token (SETUP.md step 3). The bot refreshes it every ~45 days by itself.
   - *TikTok:* click **Connect** and approve with that channel's TikTok account.
   - Click **Check logins** to test.
4. Tick **post daily at** and set a time for each channel you want live.

Try **Make video only** first. It writes and renders the next episode without posting anything,
so you can watch it (click **latest video**).

## Good to know
- **The computer has to be on and awake** at posting times with the bot running. On Windows:
  Settings → System → Power → **Sleep: Never** (when plugged in). The screen can still turn off.
  If the computer was asleep at a channel's time, that channel runs as soon as the bot notices (same day).
- **Cost:** every run uses Claude Code on your plan. Five channels a day is a fair amount of usage; start with one or two.
- **Speed:** 2D videos take ~2 minutes to render, 3D (In This Town) ~10 minutes. Runs happen one at a time.
- **Secrets** are stored in `.env` in the project folder (never committed). Don't share that file.
- **Permissions:** "Safe" lets Claude use only the commands the runbook needs. If a run stalls on a permission,
  check its log; "Full" skips all checks (only use it on a computer dedicated to this).
- **YouTube audit:** until Google approves your API project, uploads are locked private (see SETUP.md). The bot still
  makes the video; upload it by hand from the **latest video** link.
- **Finished videos:** `channels/<channel>/episodes/day-NNN/out/final.mp4`
