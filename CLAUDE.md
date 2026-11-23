# Theo Has 100 Days — automated Shorts channel

A daily cartoon series made entirely in code: the character, backgrounds and animation are SVG
(`render/`), the voices come from a local open-source TTS model (Kokoro, runs offline), and the music
and sound effects are synthesized in `scripts/build.py`. No image/video generation services.

Read `series/bible.json` (story, cast, rules) and `series/story.json` (where the story is now)
before writing anything.

## Layout

| Path | What |
|---|---|
| `series/bible.json` | Series bible: premise, arc, cast, voices, voting rules, cameo rules, safety rules, backlog |
| `series/story.json` | Live state: `next_day`, Theo's current look (`theo_state`), plot threads, every published episode + platform IDs |
| `episodes/day-NNN/episode.json` | The script for one day (you write this) |
| `episodes/day-NNN/inbox.json` | Ranked comments + cameo requests (written by `fetch_comments.py`) |
| `episodes/day-NNN/out/` | Render output (git-ignored). `final.mp4` is the video |
| `render/character.js` | The character renderer. All traits in `DEFAULT_STATE`; `guestState()` makes cameo guests |
| `render/backgrounds.js` | Scenes: basement, bathroom, barber, gym, kitchen, street, doctor_office, studio |
| `scripts/build.py` | episode.json → voices → timeline → frames → mixed MP4 (`--preview` = 3 stills only) |
| `scripts/publish.py` | Upload to YouTube / Instagram / TikTok, post vote comment, reply to winner + cameos, advance story.json |
| `scripts/fetch_comments.py` | Pull + rank comments on the last episode, flag cameo requests |

## DAILY RUNBOOK (the scheduled task runs this)

1. **Setup**: `bash scripts/bootstrap.sh && python3 scripts/check_setup.py`. If no platform is configured, stop and report.
2. **Read votes**: `python3 scripts/fetch_comments.py` → read `episodes/day-NNN/inbox.json` (NNN = `story.next_day`).
   - Day 1 has no inbox: the episode already exists.
3. **Pick the winner** using `bible.voting_rules` + `bible.safety_rules`:
   - Go down `top` by likes; take the first comment that's a doable task/plot choice, safe, kind, and not a repeat
     (check `story.episodes[].changes` and titles).
   - Off-theme but funny suggestions can be bent to fit ("fight a goose" → Theo gets chased by a goose on his first run).
   - Nothing usable → next `bible.backlog_ideas` item that hasn't happened ("Gremlin picked today").
4. **Pick cameos** using `bible.cameo_rules`: from `cameo_requests` (only `handle_ok: true`), choose up to 2 whose role
   fits the episode (a doctor for skin, a barber for a haircut…). Also count the winner if they asked for a role.
   Never reuse a handle from `story.cameos_used` in back-to-back episodes.
5. **Write `episodes/day-NNN/episode.json`** (schema below). Rules:
   - 4–6 scenes, 20–35 s total (about 60–85 spoken words). Hook in the first line.
   - Scene 1 credits the winner by handle, spoken naturally ("Top comment from sleepy frog said…" — say handles as words, no @ or digits soup).
   - At least one `transform` that visibly changes Theo (unless it's a pure plot day, then use a big reaction/pose).
   - Keep continuity: `transform.set` only changes traits; everything else carries over from `story.theo_state`.
   - Use a running gag or plot thread (Deb, Brett's bet, Nina, Gremlin) at least every other day.
   - Add a one-line `summary` (used as story memory for future days).
6. **Preview**: `python3 scripts/build.py episodes/day-NNN --preview`, look at the 3 stills (Read the PNGs). Fix anything overlapping or unreadable.
7. **Render**: `python3 scripts/build.py episodes/day-NNN` (≈1.5 min).
8. **Publish**: `python3 scripts/publish.py episodes/day-NNN`. It is idempotent: if a step fails, fix it and re-run;
   finished steps are skipped. It advances `story.json` only if at least one platform succeeded.
9. **Commit** `series/story.json` + `episodes/day-NNN/{episode.json,inbox.json,published.json}` and push.
10. **Hand-off file**: if TikTok isn't configured (or is in draft mode), or YouTube uploads are still audit-locked
    (`YT_PRIVACY` unset and the user said the audit is pending), send `episodes/day-NNN/out/final.mp4` to the user with
    SendUserFile (`status: proactive`) so they can post it from their phone. If they upload to YouTube by hand, record it later with
    `python3 scripts/publish.py episodes/day-NNN --youtube-id <id>`.
11. **Report** in 3–5 lines: winning comment, cameos, links, anything that failed, and token expiry warnings.

### episode.json schema

```json
{
  "day": 3,
  "title": ["THE UNIBROW", "IS GONE"],            // 2 lines, ALL CAPS, ≤ ~14 chars each looks best
  "accent": "#7cfc5a",                             // optional, color of title line 2
  "summary": "A commenter-doctor ripped off Theo's unibrow.",
  "chosen_comment": { "author": "@sleepyfrog22", "text": "...", "likes": 1843, "platform": "youtube", "comment_id": "..." },
  "cast": { "guest1": { "username": "@sleepyfrog22", "role": "doctor", "voice": "guest_m", "platform": "youtube", "comment_id": "..." } },
  "scenes": [
    { "bg": "doctor_office", "speaker": "narrator", "theo": { "expression": "shocked" }, "say": "..." },
    { "bg": "doctor_office", "speaker": "guest1", "others": [ { "who": "guest1", "expression": "smug" } ],
      "theo": { "expression": "sad" }, "say": "..." },
    { "bg": "doctor_office", "speaker": "theo", "others": [ { "who": "guest1" } ], "theo": { "expression": "shocked" }, "say": "...",
      "transform": { "set": { "unibrow": false, "brows": "groomed" }, "label": "RIIIP!", "after_expression": "happy" } },
    { "bg": "doctor_office", "speaker": "theo", "theo": { "expression": "happy", "pose": "flex" }, "say": "..." }
  ],
  "cta": ["TOP COMMENT DECIDES", "DAY 4"]
}
```

- `speaker`: `narrator`, `theo`, `deb`, `brett`, `nina`, or a cast key (`guest1`). Their mouth animates; voice comes from `bible.voices` (guests use `voice`: `guest_m`/`guest_f`).
- `others`: up to 2 characters on screen with Theo (`deb`, `brett`, `nina`, or cast keys). Cameo guests automatically get a name tag.
- `expression`: neutral, happy, sad, shocked, determined, smug, angry. `pose`: idle, wave, flex.
- `prop`: `letter` (more can be added in `render/player.js` → `prop()`).
- Traits for `transform.set` (see `DEFAULT_STATE` in `render/character.js`): `hair` (greasy_mess, buzz, fade, styled, curly_top, long, bun, bald),
  `hair_color`, `unibrow`, `brows` (bushy, groomed), `acne` 0–3, `eye_bags`, `glasses` (taped, none, stylish), `nose_hair`,
  `facial_hair` (patchy, none, mustache_fuzz, goatee), `teeth` (yellow, white, braces), `body` (chubby, average, fit),
  `outfit` (stained_hoodie, tshirt, jacket, gym, suit, lab_coat, apron, tracksuit, chef, cardigan, uniform), `outfit_color`,
  `smelly`, `posture` (slouch, straight), `accessories` (["chain"]).
- Need a new trait, outfit, background or prop for a story beat? Add it to `render/` (keep the same flat style, 9px ink outlines), preview it, then use it.

## Hard rules
- Follow `bible.safety_rules` and `bible.cameo_rules` exactly. Never use anything about a commenter except their public handle.
- Never post anything except through `scripts/publish.py`. Never delete or edit past uploads.
- One episode per day. If today's episode is already published (`published.json` has entries for it), don't make another.
- Don't commit secrets, `models/`, or `episodes/*/out/`.
