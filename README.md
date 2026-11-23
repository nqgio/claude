# Five automated animated Shorts channels

Made end to end by Claude Code: original characters and worlds drawn in code (SVG + three.js), local
open-source voices, synthesized music, automatic posting to YouTube Shorts / Instagram Reels / TikTok,
and stories driven by the comments.

| Channel | What |
|---|---|
| **Theo Has 100 Days** | Theo has 100 days to make every lie he told his online girlfriend true. Top comment picks each day's task. |
| **Pick Wrong** | 4-part horror stories told to YOU. Comments vote A/B at the end of every part. |
| **The Model Town** | A tiny town under glass shows how casinos, scams and apps are built to steer you, one rule a day. |
| **Last Exit** | You're the driver for people you shouldn't work for. Daily A/B choice, stats keep score. |
| **In This Town** | 3D blocky-character stories from a town where every story starts with a rule. |

- How the daily run works: `CLAUDE.md` · Connecting accounts: `SETUP.md` · Each channel: `channels/<name>/`
- Make a video: `bash scripts/bootstrap.sh && python3 scripts/build.py channels/pickwrong/episodes/day-001`
