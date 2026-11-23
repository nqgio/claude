# Setup: five channels

Everything that makes the videos is already built and works (each `channels/<name>/episodes/day-001`).
What's left is connecting your accounts so Claude can post and read comments. There are five channels:
Theo Has 100 Days, Pick Wrong, The Model Town, Last Exit and In This Town. Set up one at a time if you like. Doing it once takes about an hour, mostly
waiting on the platforms. **You can start with just one platform**: anything that isn't set up is skipped.

| Step | Time | Needed for |
|---|---|---|
| 1. Create the accounts (per channel) | 10 min | everything |
| 2. YouTube API | 20 min (+ audit wait) | posting Shorts, **reading votes**, replying |
| 3. Instagram API | 15 min | posting Reels, reading votes, replying |
| 4. TikTok API (optional) | 15 min (+ review wait) | sending videos to your TikTok drafts |
| 5. Put the keys in the cloud environment | 5 min | the daily run |
| 6. Go live | 1 min | Claude schedules the daily episode |

---

## 1. Create the accounts

Use the same name everywhere: **Theo Has 100 Days**, handle **@theohas100days** (or anything you like).
- Profile picture: `assets/brand/avatar.png`
- Bio: `Theo has 100 days to fix his life and move out of his mom's basement. YOU decide what he does. Top comment wins 👇`
- **YouTube**: create a channel on a Google account you control (youtube.com → Create a channel).
- **Instagram**: create the account, then Settings → *Account type and tools* → **Switch to professional account** → Creator.
- **TikTok**: create the account (the phone app is fine).

## 2. YouTube Data API

1. Go to **console.cloud.google.com** → create a project (e.g. `theo-shorts`).
2. *APIs & Services → Library* → search **YouTube Data API v3** → **Enable**.
3. *APIs & Services → OAuth consent screen* (newer consoles call it *Google Auth Platform*):
   - User type **External**, fill in app name + your email.
   - Under *Audience*, add your Google account as a test user, **then click "Publish app" → In production**.
     (While it's in *Testing*, Google expires the login every 7 days and the daily run would break.
     Google will say the app is unverified; that's fine for your own channel.)
4. *Credentials → Create credentials → OAuth client ID* → type **Desktop app** → download the JSON.
5. On your own computer (needs Python):
   ```bash
   pip install google-auth-oauthlib
   python3 scripts/youtube_auth.py ~/Downloads/client_secret_XXXX.json
   ```
   Sign in with the channel's Google account and allow access. It prints `YT_CLIENT_ID`,
   `YT_CLIENT_SECRET` and `YT_REFRESH_TOKEN`. Keep them for step 5.
6. **Request the API audit.** YouTube locks videos uploaded through an unaudited API project as **private**.
   Submit the *YouTube API Services Audit and Quota Extension Form* (search for that name, or go through the
   API's page in Cloud Console). Describe it honestly: "A personal channel that uploads one original animated Short per day
   and reads comments on my own videos to pick the next episode." Approval usually takes days to a few weeks.
   - **Until it's approved:** Claude can still read comments, post and reply on YouTube, and Instagram works fully.
     For YouTube, upload the daily MP4 yourself (Claude sends it to you each day), and the comment features still work on it.
     Paste the video's ID into the episode's `published.json` (Claude will ask) so comments get read.

## 3. Instagram API (Instagram Login)

1. Go to **developers.facebook.com** → *My Apps* → **Create app**. When asked for a use case, choose
   **Manage messaging & content on Instagram** (this is the "Instagram API with Instagram Login").
2. In the app, open *Instagram → API setup with Instagram login*.
3. Under **Generate access tokens**, click *Add account*, log in to the Theo Instagram account, and approve
   the permissions `instagram_business_basic`, `instagram_business_content_publish` and
   `instagram_business_manage_comments`.
4. Click **Generate token**. Copy the token as `IG_ACCESS_TOKEN`, and the account's numeric ID shown next to it as `IG_USER_ID`.
5. The app can stay in *Development* mode because it only posts to your own account.
6. **The token lasts 60 days.** Around day 50, ask Claude to "refresh the Instagram token". It runs
   `scripts/refresh_tokens.py`, and you replace the value in step 5's settings.

## 4. TikTok (optional, can wait)

TikTok has **no API for reading comments**, so votes come from YouTube + Instagram, and the same video goes to TikTok.
1. **developers.tiktok.com** → *Manage apps* → **Connect an app**. Add the products **Login Kit** and **Content Posting API**.
   Add the scopes `video.upload` (and `video.publish` if you want direct posting later).
2. Under Login Kit, add a **Redirect URI**: any https page you control (it may 404, that's fine).
3. Submit the app for review (they want an app description, a website and a short demo video. The Day 1 MP4 + a screen recording works).
4. Once approved, on your computer: `python3 scripts/tiktok_auth.py <client_key> <client_secret> <redirect_uri>` → follow the prompts.
   It prints `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN` (valid 1 year).
5. By default videos land in your **TikTok inbox as drafts** (`TIKTOK_MODE=draft`). Open TikTok, tap the notification, then Post.
   After TikTok audits your app for direct posting you can set `TIKTOK_MODE=direct`.
   **Until then:** Claude sends you the MP4 each day; post it from your phone.

## 5. Put the keys in the cloud environment

**Each channel's account keys get the channel's prefix** so they can never post to the wrong account:

| Channel | Prefix |
|---|---|
| Theo Has 100 Days | `THEO_` |
| Pick Wrong | `PICKWRONG_` |
| The Model Town | `MODELTOWN_` |
| Last Exit | `LASTEXIT_` |
| In This Town | `INTHISTOWN_` |

The app-level values (`YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`) can be shared
without a prefix, because one Google project and one TikTok app can serve all channels. Run `youtube_auth.py` once per channel,
signing in to that channel's Google account / brand channel each time, and generate one Instagram token per Instagram account.

Example for Theo + Pick Wrong:
```
YT_CLIENT_ID=...            (shared)
YT_CLIENT_SECRET=...        (shared)
THEO_YT_REFRESH_TOKEN=...
THEO_IG_USER_ID=...
THEO_IG_ACCESS_TOKEN=...
PICKWRONG_YT_REFRESH_TOKEN=...
PICKWRONG_IG_USER_ID=...
PICKWRONG_IG_ACCESS_TOKEN=...
```

### Where to put them

In the Claude app, open this session's **cloud environment menu** (title bar) → **Edit** → **Environment variables**, and add them.
Optional per channel: `<PREFIX>_YT_PRIVACY=private` (test uploads), `<PREFIX>_TIKTOK_MODE=direct`.

**Use a personal environment only** (Claude set one up for this project). Anyone who can use an environment can read its variables.
**Never paste these keys into the chat.**

Then start a new session and ask Claude to "run the setup check". That runs `python3 scripts/check_setup.py`,
which tests each login without posting anything.

## 6. Go live

Tell Claude what times you want each channel's daily episode (spread them out, e.g. 11am, 1pm, 4pm, 6pm, 8pm your time).
Claude creates one scheduled task per channel, each running the daily runbook in `CLAUDE.md`:

> read yesterday's comments → pick the winner + cameo guests → write the episode → render → post everywhere →
> post the "what should Theo do tomorrow?" comment → reply to the winner and the cameo guests → commit the story → send you a summary.

Day 1 is already written and rendered, so the first run just publishes it.

### Things only you can do (no API exists)
- **Pin** the "vote for tomorrow" comment (optional, about 5 seconds in the app; it helps engagement).
- YouTube **Community polls**: no API, so "polls" here are the most-liked comment.
- Reply to comments in your own voice whenever you want. Claude only replies to the daily winner and cameo guests.
