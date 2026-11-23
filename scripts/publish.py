#!/usr/bin/env python3
"""Publish a rendered episode everywhere that's configured, post the vote comment,
reply to the winner + cameo commenters, and advance series/story.json.

Usage: python3 scripts/publish.py episodes/day-002 [--dry-run] [--youtube-id VIDEO_ID]
  --youtube-id  record a Short you uploaded by hand (e.g. before the API audit), so its comments get read
                and the vote comment / replies are posted on it
Safe to re-run: finished steps are recorded in <episode>/published.json and skipped.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from platforms import youtube, instagram, tiktok  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def final_state(start, ep):
    s = dict(start)
    for sc in ep["scenes"]:
        if sc.get("transform"):
            s.update(sc["transform"]["set"])
    return s


def main(ep_dir: Path, dry=False):
    ep = json.loads((ep_dir / "episode.json").read_text())
    story = json.loads((ROOT / "series/story.json").read_text())
    bible = json.loads((ROOT / "series/bible.json").read_text())
    video = ep_dir / "out/final.mp4"
    assert video.exists(), f"render first: {video} missing"
    assert ep["day"] == story["next_day"], f"episode is day {ep['day']} but story expects day {story['next_day']}"
    day, nxt = ep["day"], ep["day"] + 1
    l1, l2 = ep["title"]
    pretty = f"{l1} {l2}".title()
    yt_title = ep.get("yt_title") or f"Day {day}: {pretty} #shorts"
    credit = f"\nToday's pick came from {ep['chosen_comment']['author']} 🏆" if ep.get("chosen_comment") else ""
    caption = ep.get("caption") or (
        f"Day {day}/100: {pretty}{credit}\n\n"
        f"Theo has 100 days to fix his life and move out of his mom's basement. YOU decide what he does next. "
        f"Most-liked comment picks Day {nxt}. Want a cameo? Comment who you'd be (doctor, barber, coach…) 🎬\n\n"
        f"#glowup #theohas100days #animation #storytime #fyp")
    vote = (f"🗳️ What should Theo do on DAY {nxt}? Most-liked comment wins 👇\n"
            f"🎬 Want to be in it? Comment “I'll be the ___” (doctor, barber, coach, interviewer…)")

    log_path = ep_dir / "published.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {}

    def step(key, fn):
        if key in log:
            print(f"skip {key} (done)"); return log[key]
        if dry:
            print(f"[dry-run] would run {key}"); return None
        try:
            log[key] = fn()
            print(f"ok   {key}: {log[key]}")
        except Exception as e:  # keep going on other platforms
            print(f"FAIL {key}: {e}")
            return None
        log_path.write_text(json.dumps(log, indent=2))
        return log[key]

    manual = sys.argv[sys.argv.index("--youtube-id") + 1] if "--youtube-id" in sys.argv else None
    if manual and "youtube" not in log:
        log["youtube"] = {"id": manual, "url": f"https://youtube.com/shorts/{manual}", "manual": True}
        log_path.write_text(json.dumps(log, indent=2))
    if youtube.configured():
        yt = step("youtube", lambda: youtube.upload(str(video), yt_title, caption, ["glow up", "animation", "theo has 100 days", "storytime"]))
        if yt: step("youtube_vote_comment", lambda: youtube.comment(yt["id"], vote))
    else:
        print("youtube: not configured, skipping")
    if instagram.configured():
        ig = step("instagram", lambda: instagram.upload(str(video), caption))
        if ig: step("instagram_vote_comment", lambda: instagram.comment(ig["id"], vote))
    else:
        print("instagram: not configured, skipping")
    if tiktok.configured():
        step("tiktok", lambda: tiktok.upload(str(video), caption))
    else:
        print("tiktok: not configured, skipping")

    # replies to the winner and cameo guests (on the platform their comment came from)
    link = (log.get("youtube") or {}).get("url") or (log.get("instagram") or {}).get("url") or ""
    mods = {"youtube": youtube, "instagram": instagram}
    cc = ep.get("chosen_comment")
    if cc and cc.get("comment_id") and cc.get("platform") in mods and mods[cc["platform"]].configured():
        step("reply_winner", lambda: mods[cc["platform"]].reply(cc["comment_id"], f"Your comment won Day {day} 🏆 Go watch: {link}"))
    for key, g in (ep.get("cast") or {}).items():
        if g.get("comment_id") and g.get("platform") in mods and mods[g["platform"]].configured():
            step(f"reply_cameo_{key}", lambda g=g: mods[g["platform"]].reply(g["comment_id"], f"You're in Day {day} as the {g.get('role','guest')} 👀🎬 {link}"))

    if dry:
        return
    if not any(k in log for k in ("youtube", "instagram", "tiktok")):
        print("Nothing was published; story.json NOT advanced."); sys.exit(1)
    end = final_state(story["theo_state"], ep)
    story["episodes"].append({
        "day": day, "title": ep["title"], "summary": ep.get("summary", ""),
        "chosen_comment": cc, "cameos": [g["username"] for g in (ep.get("cast") or {}).values()],
        "youtube": log.get("youtube"), "instagram": log.get("instagram"), "tiktok": log.get("tiktok"),
        "changes": [sc["transform"]["set"] for sc in ep["scenes"] if sc.get("transform")],
    })
    story["cameos_used"] += [g["username"] for g in (ep.get("cast") or {}).values()]
    story["theo_state"] = end
    story["next_day"] = nxt
    (ROOT / "series/story.json").write_text(json.dumps(story, indent=2, ensure_ascii=False) + "\n")
    print(f"story.json advanced to day {nxt}")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), dry="--dry-run" in sys.argv)
