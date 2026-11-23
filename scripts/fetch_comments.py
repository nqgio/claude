#!/usr/bin/env python3
"""Pull comments from the most recent published episode, rank them, and flag cameo requests.

Usage: python3 scripts/fetch_comments.py            -> writes episodes/day-NNN/inbox.json for the NEXT day
Claude reads inbox.json, applies the voting + cameo rules from series/bible.json, and writes the next episode.
"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from platforms import youtube, instagram  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

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


def main():
    story = json.loads((ROOT / "series/story.json").read_text())
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
    out_dir = ROOT / f"episodes/day-{day:03d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    inbox = {
        "for_day": day, "source_day": last["day"], "total": len(comments),
        "top": comments[:40],
        "cameo_requests": [c for c in comments if c["cameo_role"]][:20],
    }
    (out_dir / "inbox.json").write_text(json.dumps(inbox, indent=2, ensure_ascii=False))
    print(f"{len(comments)} comments -> {out_dir / 'inbox.json'}")
    for c in comments[:10]:
        flag = f"  [CAMEO: {c['cameo_role']}]" if c["cameo_role"] else ""
        print(f"{c['likes']:>6}  {c['platform'][:2]}  {c['author']}: {c['text'][:90]}{flag}")


if __name__ == "__main__":
    main()
