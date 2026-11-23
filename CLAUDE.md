# Five automated Shorts channels, one engine

Daily animated series made entirely in code: characters, backgrounds and animation are SVG or three.js
(`render/`), voices come from a local open-source TTS model (Kokoro, offline), music and sound effects
are synthesized in `scripts/build.py`. No image/video generation services.

| Channel | Folder | Style | Format |
|---|---|---|---|
| Theo Has 100 Days | `channels/theo` | `theo` (flat cartoon) | Daily glow-up; top comment picks the task; commenter cameos |
| Pick Wrong | `channels/pickwrong` | `horror` (dark flat, stick figure) | 4-part horror stories, A/B vote each part |
| The Model Town | `channels/modeltown` | `diorama` (town under glass + giant hand) | "N rules" explainers, one rule per day |
| Last Exit | `channels/lastexit` | `crime` (night city, stats HUD) | Ongoing second-person crime saga, A/B vote daily |
| In This Town | `channels/inthistown` | `blocky` (3D, three.js) | Town-rule mini stories, vote on what the character does |

Each channel folder: `channel.json` (style, music, credential prefix, title/caption templates),
`bible.json` (premise, voices, rules, scene vocabulary, backlog: **read it before writing**),
`story.json` (live state + every published episode), `episodes/day-NNN/` (episode.json, inbox.json, published.json, out/).

## Shared tools

| Path | What |
|---|---|
| `scripts/build.py <episode dir> [--preview]` | voices → timeline → frames → mixed MP4. `--preview` renders stills (hook, one per scene, CTA) |
| `scripts/publish.py <episode dir> [--dry-run]` | upload to the channel's YouTube/Instagram/TikTok, post vote comment, reply to winner + cameos, advance story.json |
| `scripts/fetch_comments.py <channel>` | rank comments, flag cameo requests, tally A/B votes → next day's inbox.json |
| `scripts/check_setup.py` | verify tools + every channel's logins (read-only) |
| `render/players/<style>.js` | one renderer per style; `render/character.js` (flat characters), `render/backgrounds.js` (Theo) |

## Writing episodes (all channels)
- `say`: narration. Wrap ONE keyword per sentence in `*asterisks*` → highlighted in captions (green/yellow per style).
- Narration style: short punchy sentences, rhetorical questions, exclamations; it makes the TTS sound more alive.
- `speaker`: `narrator` or a voice key from the bible (`theo`, `deb`, `stranger`, `neighbor`, guest keys...).
- `sfx`: `["boom", {"name": "knock", "at": 1.2, "gain": 0.8}]`, available: pop ding poof sparkle whoosh boom knock heartbeat stamp tick doorbell glitch riser click.
- `hold`: extra seconds after the line. `flash`: white cut. `zoom`: push-in amount.
- `pronounce`: spoken-only respellings. The build prints `pronunciation check` lines for words like lives/live/read/lead/close.
  Read the phonemes (`lˈaɪvz` = "life-s", `lˈɪvz` = "livs"); reword ("Still lives") or respell if wrong.
- `cta` for vote channels: `{"question_lines": [...], "options": [{"label", "color", "keywords": [...]}], "prompt"}`. Keywords drive vote counting.
- Scene vocabulary per style is in each bible's `scene_types`. Need something new (a room, prop, pose)? Add it to the style's player, preview it, then use it.
- Keep every channel's stories original. Never use another channel's characters, names or story beats.

## DAILY RUNBOOK (one scheduled task per channel runs this with its channel name)

1. `bash scripts/bootstrap.sh && python3 scripts/check_setup.py`. If the channel has no platform configured, stop and report.
2. `python3 scripts/fetch_comments.py <channel>` → read `channels/<channel>/episodes/day-NNN/inbox.json` (NNN = story.next_day).
   Day 1 already exists for every channel: just build + publish it.
3. Decide what happens using the bible's `voting_rules` + `safety_rules`:
   - Theo: most-liked usable comment = today's task (see Theo notes below).
   - Vote channels (pickwrong, lastexit, inthistown): `inbox.choice_tally` decides; open with the result ("62% of you opened the door" / a stamp).
   - Model Town: next rule of the current topic; on a topic's last day, top comment picks the next topic.
   - Cameos: from `cameo_requests` with `handle_ok: true`, max 2, only where a role fits.
4. Write `episodes/day-NNN/episode.json` following the bible + the previous episode's format. Update the story arc as needed. Add `summary`.
5. `python3 scripts/build.py <ep> --preview` → Read the stills. Fix overlaps, off-screen characters (3D: cameras inside houses or subjects outside the narrow portrait frame), unreadable captions.
6. `python3 scripts/build.py <ep>` (2D ≈ 1.5 min, 3D ≈ 9 min).
7. `python3 scripts/publish.py <ep>`. It is idempotent; re-run after fixing failures. It advances story.json only if something was published.
8. Commit `channels/<channel>/story.json` + the episode's json files and push.
9. If TikTok is in draft mode/unconfigured or YouTube is audit-locked, send `out/final.mp4` to the user with SendUserFile (status proactive).
10. Report in 3-5 lines: what the votes decided, cameos, links, failures, token-expiry warnings.

## Theo notes
- Story: Pixie (online girlfriend) lands Day 100; the 8 lies; secret Nina reveal. See `channels/theo/bible.json`.
- Pick the most-liked comment that's doable, safe, kind and not a repeat. Bend funny off-theme ones to fit. Nothing usable → backlog.
- At least one `transform` per episode; keep continuity with `story.theo_state`.

### Theo episode.json schema

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
- `texts`: phone chat on screen, bubbles pop in one by one with a notification sound: `[{"from": "pixie", "text": "i booked my flight", "heart": true}, {"from": "theo", "text": "WHAT"}]`. Optional `texts_title` (default `pixie <3`). Keep each message under ~45 characters.
- Traits for `transform.set` (see `DEFAULT_STATE` in `render/character.js`): `hair` (greasy_mess, buzz, fade, styled, curly_top, long, bun, bald),
  `hair_color`, `unibrow`, `brows` (bushy, groomed), `acne` 0–3, `eye_bags`, `glasses` (taped, none, stylish), `nose_hair`,
  `facial_hair` (patchy, none, mustache_fuzz, goatee), `teeth` (yellow, white, braces), `body` (chubby, average, fit),
  `outfit` (stained_hoodie, tshirt, jacket, gym, suit, lab_coat, apron, tracksuit, chef, cardigan, uniform), `outfit_color`,
  `smelly`, `posture` (slouch, straight), `accessories` (["chain"]).
- Need a new trait, outfit, background or prop for a story beat? Add it to `render/` (keep the same flat style, 9px ink outlines), preview it, then use it.

## Hard rules
- Follow each bible's safety and cameo rules exactly. Never use anything about a commenter except their public handle.
- Post only via `scripts/publish.py`. Never delete or edit past uploads. One episode per channel per day.
- Credentials are per channel (`<PREFIX>_YT_REFRESH_TOKEN`, ...). Never copy one channel's keys to another.
- Never add echo/reverb to voices (it sounds robotic). Don't commit secrets, `models/`, or `episodes/*/out/`.
