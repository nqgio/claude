#!/usr/bin/env python3
"""Pull comments from the most recent published episode, rank them, and flag cameo requests.

Usage: python3 scripts/fetch_comments.py <channel>   (e.g. theo, pickwrong)
  -> writes channels/<channel>/episodes/day-NNN/inbox.json for the NEXT day
Claude reads inbox.json, applies the voting + cameo rules from the channel's bible.json, and writes the next episode.
For choice channels (story.pending_choice set) it also tallies A/B votes into inbox["choice_tally"].
"""
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8"); _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import channel as chmod  # noqa: E402

END = r"\s*(?:[?.!,]|$|\b(?:for|in|pl[sz]|please|and|so|to|who|that|lol|lmao|haha|bc|because)\b)"
CAMEO_PATTERNS = [
    r"\b(?:can|could|may)\s+i\s+(?:be|play)\s+(?:the|his|a|an|theo'?s)?\s*([a-z][a-z ]{1,24}?)" + END,
    r"\b(?:let|make)\s+me\s+(?:be\s+|play\s+)?(?:the|his|a|an|theo'?s)\s+([a-z][a-z ]{1,24}?)" + END,
    r"\bi(?:'ll|’ll| will|'d| would| wanna| want to| can)\s+(?:be|play)\s+(?:the|his|a|an|theo'?s)\s+([a-z][a-z ]{1,24}?)" + END,
    r"\bcast\s+me\s+as\s+(?:the|his|a|an)?\s*([a-z][a-z ]{1,24}?)" + END,
    r"\bput\s+me\s+in\s+(?:it|the video|day \d+)\s+as\s+(?:the|his|a|an)?\s*([a-z][a-z ]{1,24}?)" + END,
]
BAD_HANDLE = re.compile(r"(sex|porn|nsfw|onlyfans|nazi|hitler|kill|rape|\bn[i1]gg|f[a@]g|official|support|admin|\b1[0-7]\b|\byo\b)", re.I)


def cameo_role(text):
    t = text.lower()
    for p in CAMEO_PATTERNS:
        m = re.search(p, t)
        if m:
            role = m.group(1).strip()
            role = re.sub(r"\b(and|but|so|lol|lmao|haha)\b.*$", "", role).strip()
            if 2 <= len(role) <= 24:
                return role
    return None


def tally(comments, options):
    counts = [0] * len(options)
    for c in comments:
        t = " " + re.sub(r"[^a-z0-9 ]", " ", c["text"].lower()) + " "
        for i, o in enumerate(options):
            kws = [k.lower() for k in o.get("keywords", [])] + [o["label"].lower()]
            if any((" " + k + " ") in t if len(k) <= 2 else k in t for k in kws):
                counts[i] += 1
                break
    total = sum(counts) or 1
    return [{"label": o["label"], "votes": n, "percent": round(100 * n / total)} for o, n in zip(options, counts)]


def main():
    ch = chmod.channel_dir(sys.argv[1] if len(sys.argv) > 1 else "theo")
    cfg, story = chmod.load(ch)["channel"], chmod.load(ch)["story"]
    chmod.use_credentials(cfg)
    from platforms import youtube, instagram  # noqa: E402
    if not story["episodes"]:
        print("No published episodes yet; nothing to fetch.")
        return
    last = story["episodes"][-1]
    comments = []
    if last.get("youtube") and youtube.configured():
        comments += youtube.fetch_comments(last["youtube"]["id"])
    if last.get("instagram") and instagram.configured():
        comments += instagram.fetch_comments(last["instagram"]["id"])
    for c in comments:
        role = cameo_role(c["text"])
        c["cameo_role"] = role
        c["handle_ok"] = not BAD_HANDLE.search(c["author"]) and len(c["author"]) <= 31
    comments.sort(key=lambda c: (c["likes"], c["replies"]), reverse=True)
    day = story["next_day"]
    out_dir = ch / f"episodes/day-{day:03d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    inbox = {
        "for_day": day, "source_day": last["day"], "total": len(comments),
        "top": comments[:40],
        "cameo_requests": [c for c in comments if c["cameo_role"]][:20],
    }
    if story.get("pending_choice"):
        inbox["choice_tally"] = tally(comments, story["pending_choice"]["options"])
        print("vote split:", ", ".join(f"{x['label']} {x['percent']}% ({x['votes']})" for x in inbox["choice_tally"]))
    (out_dir / "inbox.json").write_text(json.dumps(inbox, indent=2, ensure_ascii=False))
    print(f"{len(comments)} comments -> {out_dir / 'inbox.json'}")
    for c in comments[:10]:
        flag = f"  [CAMEO: {c['cameo_role']}]" if c["cameo_role"] else ""
        print(f"{c['likes']:>6}  {c['platform'][:2]}  {c['author']}: {c['text'][:90]}{flag}")


if __name__ == "__main__":
    main()
