"""Listing content: eBay title, HTML description, item specifics, category."""
from __future__ import annotations

import html
import re

from .. import activity, config
from .. import settings_store as st
from ..providers.base import ProductData

TITLE_MAX = 80
ACRONYMS = {"USB", "LED", "LCD", "HDMI", "BPA", "UV", "XL", "XXL", "PVC", "ABS", "DIY", "AC", "DC", "GPS", "TV", "HD",
            "4K", "RGB", "PC", "USA", "US", "FDA", "EVA", "TPU", "PU", "PET", "PP", "OZ", "ML", "MM", "CM", "IN", "FT",
            "LB", "LBS", "QT", "II", "III", "IV", "MAX", "PRO", "2-IN-1", "3-IN-1", "316L", "304"}
JUNK_PATTERNS = [
    r"amazon'?s? choice", r"\bamazon\b", r"\bprime\b", r"best ?sell(?:er|ing)", r"#\s?1\b", r"\bhot sale\b",
    r"\bfree shipping\b", r"\bnew arrival\b", r"\bnewest\b", r"\blatest\b", r"\b20\d\d (?:upgraded|version|new|model)\b",
    r"\bupgraded\b", r"\blimited time\b", r"\b(?:great |perfect |ideal )?gifts? (?:for|idea)[^,|]*", r"\b100% ?(?:brand )?new\b",
    r"\bauthentic\b", r"\bgenuine\b", r"\boriginal\b",
]
JUNK_RE = re.compile("|".join(JUNK_PATTERNS), re.I)
SPLIT_RE = re.compile(r"\s*(?:[,|;]|\s[-–—]\s|【|】|\[|\]|:)\s*")
DANGLING = {"with", "and", "for", "&", "-", "of", "the", "to", "in", "or", "by", "a", "an", "+"}
MARKETING_RE = re.compile(r"\b(we|our|us|warranty|guarantee|customer service|contact|amazon|refund|money[- ]back|"
                          r"risk[- ]free|satisfaction|worry[- ]free|after[- ]sales?|email|hesitate)\b", re.I)
FILLER = [(r"\b(very|really|extremely|super|ultra|truly|absolutely)\s+", ""),
          (r"\b(perfect|ultimate|amazing|awesome|incredible|best|premium|top[- ]quality|high[- ]quality)\s+", ""),
          (r"\bis made (?:of|from)\b", "uses"), (r"\bmade (?:of|from)\b", "built from"), (r"\bwill not\b", "won't"),
          (r"\bdoes not\b", "doesn't"), (r"\bin order to\b", "to"), (r"\ballows you to\b", "lets you"),
          (r"\bit is\b", "it's"), (r"\bdesigned to\b", "built to")]


def _strip_symbols(t: str) -> str:
    t = re.sub(r"[™®©℠]", "", t)
    t = re.sub(r"[\U00010000-\U0010ffff☀-➿]", "", t)  # emoji / dingbats
    return re.sub(r"\s+", " ", t).strip()


def _fix_case(word: str) -> str:
    core = re.sub(r"[^A-Za-z0-9\-]", "", word)
    if core.upper() in ACRONYMS or len(core) <= 2:
        return word
    if core.isupper() and len(core) > 3:
        return word.capitalize() if word[:1].isalpha() else word.lower()
    return word


def make_title(product_title: str, brand: str = "") -> str:
    t = _strip_symbols(product_title)
    segments, seen_words = [], set()
    for seg in SPLIT_RE.split(t):
        seg = JUNK_RE.sub(" ", seg)
        seg = re.sub(r"\s+", " ", seg).strip(" -–—/&+")
        if not seg:
            continue
        words = [w.lower() for w in re.findall(r"[A-Za-z0-9']+", seg)]
        if words and all(w in seen_words for w in words):
            continue  # pure repetition → keyword stuffing
        seen_words.update(words)
        segments.append(" ".join(_fix_case(w) for w in seg.split()))
    out = ""
    for seg in segments:
        candidate = f"{out} {seg}".strip()
        if len(candidate) <= TITLE_MAX:
            out = candidate
            continue
        # fit as many words of this segment as possible, then stop
        for w in seg.split():
            if len(f"{out} {w}".strip()) <= TITLE_MAX:
                out = f"{out} {w}".strip()
            else:
                break
        break
    words = out.split()
    # never end on a connector or a stranded number ("...Fresh for 3")
    while words and (words[-1].lower().strip(",") in DANGLING or words[-1].isdigit()):
        words.pop()
    return " ".join(words)[:TITLE_MAX] or product_title[:TITLE_MAX]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def rewrite_feature(feature: str) -> tuple[str, str]:
    """Return (label, condensed text) for one Amazon bullet."""
    f = _strip_symbols(feature)
    label, body = "", f
    m = re.match(r"^\s*[\[【(]?([A-Za-z0-9 &/'+\-]{3,40})[\]】)]?\s*[:：\-–—]\s+(.+)$", f) or \
        re.match(r"^\s*[\[【]([^\]】]{3,40})[\]】]\s*(.+)$", f)
    if m:
        label, body = m.group(1).strip(), m.group(2).strip()
    label = " ".join(w.capitalize() if w.isupper() and w.upper() not in ACRONYMS else w for w in label.split())
    kept = [s for s in _sentences(body) if not MARKETING_RE.search(s)][:2]
    text = " ".join(kept)
    for pat, rep in FILLER:
        text = re.sub(pat, rep, text, flags=re.I)
    text = " ".join(_fix_case(w) for w in text.split())
    if len(text) > 220:
        text = text[:220].rsplit(" ", 1)[0].rstrip(",;:") + "."
    if text:
        text = text[0].upper() + text[1:]
    return label, text


SPEC_KEYS = ["Brand", "Model", "Item model number", "Material", "Color", "Size", "Capacity", "Product Dimensions",
             "Item Weight", "Number of Items", "Number of Pieces", "Power Source", "Style", "Finish Type", "Length"]


def make_description(p: ProductData, title: str, handling_days: int, overview: str | None = None,
                     bullets: list[str] | None = None) -> str:
    e = html.escape
    if not overview:
        mat, col = p.details.get("Material"), p.details.get("Color")
        finish = " ".join(x.lower() for x in (col, mat) if x)
        made = " ".join(x for x in ([f"By {p.brand}"] if p.brand else []) + ([f"in {finish}"] if finish else []))
        overview = (made + ". " if made else "") + "Brand new and unused, shipped in the manufacturer's packaging."
    if bullets is None:
        bullets = []
        for f in p.features[:6]:
            label, text = rewrite_feature(f)
            if text:
                bullets.append(f"<strong>{e(label)}:</strong> {e(text)}" if label else e(text))
    else:
        bullets = [e(b) for b in bullets]
    specs = [(k, p.details[k]) for k in SPEC_KEYS if p.details.get(k)]
    if p.brand and not any(k == "Brand" for k, _ in specs):
        specs.insert(0, ("Brand", p.brand))
    rows = "".join(f"<tr><td style='padding:4px 12px 4px 0;color:#555'>{e(k)}</td><td style='padding:4px 0'>{e(v[:120])}</td></tr>"
                   for k, v in specs[:12])
    days = "1 business day" if handling_days == 1 else f"{handling_days} business days"
    highlights = ('<ul>' + ''.join(f'<li style="margin-bottom:6px">{b}</li>' for b in bullets) + '</ul>') if bullets else ''
    spec_table = f'<table style="border-collapse:collapse;font-size:14px">{rows}</table>' if rows else ''
    template = st.get("description_template")
    if template:
        imgs = {f"img{i + 1}": (f'<img src="{e(u)}" style="max-width:100%;margin:6px 0" alt="">' if i < len(p.images) else "")
                for i, u in enumerate((p.images + ["", "", ""])[:3])}
        values = {"title": e(title), "overview": e(overview), "highlights": highlights, "specs": spec_table,
                  "brand": e(p.brand), "handling_days": e(days), **imgs}
        out = re.sub(r"<script\b.*?</script>|\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", template, flags=re.I | re.S)
        return re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda m: values.get(m.group(1), m.group(0)), out)
    return f"""<div style="font-family:Arial,Helvetica,sans-serif;max-width:900px;color:#222;line-height:1.5">
<h2 style="font-size:20px;margin:0 0 12px">{e(title)}</h2>
<p>{e(overview)}</p>
{'<h3 style="font-size:16px;margin:18px 0 6px">Highlights</h3>' + highlights if highlights else ''}
{'<h3 style="font-size:16px;margin:18px 0 6px">Specifications</h3>' + spec_table if spec_table else ''}
<h3 style="font-size:16px;margin:18px 0 6px">Shipping &amp; returns</h3>
<p>Ships within {days} of payment with tracking. Returns are accepted according to the return policy shown on this listing.</p>
</div>"""


# ---- item specifics ---------------------------------------------------------------

ASPECT_SOURCES = {
    "Brand": ["Brand", "Manufacturer"],
    "MPN": ["Item model number", "Manufacturer Part Number", "Part Number", "Model Number"],
    "Model": ["Model Name", "Model", "Item model number"],
    "Color": ["Color", "Colour"], "Material": ["Material"], "Size": ["Size"], "Style": ["Style"],
    "Item Weight": ["Item Weight"], "Number in Pack": ["Number of Items", "Unit Count", "Number of Pieces"],
    "Power Source": ["Power Source"], "Capacity": ["Capacity"], "Finish": ["Finish Type", "Finish"],
    "Pattern": ["Pattern"], "Shape": ["Shape"], "Theme": ["Theme"], "UPC": ["UPC"], "Item Length": ["Length", "Item Length"],
    "Country/Region of Manufacture": ["Country of Origin"],
}


def _clip(v: str) -> str:
    return re.sub(r"\s+", " ", v).strip()[:65]


_UNITS = {"in": "in", "inch": "in", "inches": "in", '"': "in", "cm": "cm", "centimeters": "cm", "mm": "mm",
          "millimeters": "mm", "ft": "ft", "feet": "ft", "m": "m", "meters": "m"}
_NUM = r"(\d+(?:\.\d+)?)"


def parse_dimensions(details: dict) -> dict[str, str]:
    """'10"L x 5"W x 3"H', '12 x 8 x 4 inches', '30 x 20 x 10 cm; 1.2 Pounds' → {"Item Length": "10 in", ...}."""
    out: dict[str, str] = {}

    def rank(k: str) -> int:  # the product's own size first, the shipping box last
        k = k.lower()
        return 0 if "product" in k else 1 if "item" in k else 3 if "package" in k or "box" in k else 2

    # Any "…Dimensions…" line, whatever Amazon calls it ("Item Dimensions D x W x H", "Product Dimensions"…)
    keys = sorted((k for k, v in details.items() if v and ("dimension" in k.lower() or k.strip().lower() == "size")),
                  key=rank)
    for key in keys:
        raw = details[key]
        text = raw.replace("″", '"').replace("”", '"')
        dims = text.split(";")[0]
        unit_m = re.search(r'(inches|inch|in\b|"|centimeters|cm\b|millimeters|mm\b|feet|ft\b|meters|m\b)', dims, re.I)
        unit = _UNITS.get(unit_m.group(1).lower(), "in") if unit_m else "in"
        parts = re.findall(_NUM + r'\s*(?:"|in(?:ches)?|cm|mm)?\s*([LWHD])?\b', dims)
        nums = [(float(n), (lab or "").upper()) for n, lab in parts][:3]
        if len(nums) >= 2:
            labeled = {lab: n for n, lab in nums if lab}
            order = [n for n, _ in nums]
            fmt = lambda v: f"{v:g} {unit}"  # noqa: E731
            out["Item Length"] = fmt(labeled.get("L", order[0]))
            out["Item Width"] = fmt(labeled.get("W", order[1]))
            third = order[2] if len(order) > 2 else None
            h = labeled.get("H", third if "D" not in labeled or "H" in labeled else None)
            d = labeled.get("D", h)
            if h is not None:
                out["Item Height"] = fmt(h)
            if d is not None:
                out["Item Depth"] = fmt(d)
        w = re.search(_NUM + r"\s*(pounds|pound|lbs?|ounces|ounce|oz|kilograms|kg|grams|g)\b", text, re.I)
        if w:
            out["Item Weight"] = f"{float(w.group(1)):g} {w.group(2)}"
        if out:
            break
    for name, keys in (("Item Weight", ("Item Weight", "Weight")), ("Item Length", ("Item Length", "Length")),
                       ("Item Width", ("Item Width", "Width")), ("Item Height", ("Item Height", "Height"))):
        v = next((details[k] for k in keys if details.get(k)), None)
        if v and name not in out:
            out[name] = _clip(v)
    return out


def build_aspects(p: ProductData, category_aspects: list[dict] | None = None) -> tuple[dict[str, list[str]], list[str]]:
    """Map Amazon details → eBay item specifics. Returns (aspects, missing_required_names)."""
    aspects: dict[str, list[str]] = {}
    for name, keys in ASPECT_SOURCES.items():
        for k in keys:
            if p.details.get(k):
                aspects[name] = [_clip(p.details[k])]
                break
    for name, val in parse_dimensions(p.details).items():
        aspects.setdefault(name, [val])
    aspects["Brand"] = [_clip(p.brand)] if p.brand else aspects.get("Brand", ["Unbranded"])
    aspects.setdefault("MPN", ["Does Not Apply"])
    missing = []
    if category_aspects:
        lower_details = {k.lower(): v for k, v in p.details.items()}
        for a in category_aspects:
            name = a["name"]
            restricted = a["mode"] == "SELECTION_ONLY" and a["values"]

            def allowed(v):
                if not v or not restricted:
                    return v
                return next((x for x in a["values"] if x.lower() == v.lower()), None)

            val = allowed(aspects.get(name, [None])[0])
            if not val:
                val = allowed(lower_details.get(name.lower()))
            if not val:  # close names: "Material" ↔ "Material Type", "Color" ↔ "Color Name"
                nl = name.lower()
                val = allowed(next((v for k, v in lower_details.items() if v and (k.startswith(nl + " ") or
                                                                                 nl.startswith(k + " "))), None))
            if not val and name == "Type" and p.category:
                val = allowed(p.category.split(">")[-1].strip())
            if not val and restricted:
                hay = p.title.lower()
                val = next((v for v in sorted(a["values"], key=len, reverse=True) if len(v) > 2 and v.lower() in hay), None)
            if val:
                aspects[name] = [_clip(val)]
            else:
                aspects.pop(name, None)
                if a["required"]:
                    missing.append(name)
    return dict(list(aspects.items())[:45]), missing


# ---- category ----------------------------------------------------------------------

def pick_category(title: str) -> tuple[str | None, str, str]:
    """Return (category_id, category_name, note) using eBay Taxonomy category suggestions."""
    from ..ebay import api
    from ..ebay.client import EbayError

    query = " ".join(title.split()[:12])
    try:
        sugg = api.category_suggestions(query)
    except EbayError as exc:
        return None, "", f"category lookup unavailable: {exc}"
    if not sugg:
        return None, "", "eBay returned no category suggestions"
    best = sugg[0]
    return best["id"], (best["path"] + " > " if best["path"] else "") + best["name"], ""


# ---- optional AI writer -------------------------------------------------------------------

def ai_content(p: ProductData) -> tuple[str, str, list[str]] | None:
    """Ask Claude for an original title/overview/bullets. Returns None on any problem."""
    if not st.get("ai_content_enabled") or not config.env("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        from pydantic import BaseModel

        class Copy(BaseModel):
            title: str
            overview: str
            bullets: list[str]

        source = "\n".join([f"Title: {p.title}", f"Brand: {p.brand}", f"Category: {p.category}",
                            "Features:", *[f"- {f}" for f in p.features[:8]],
                            "Details:", *[f"- {k}: {v}" for k, v in list(p.details.items())[:15]]])
        prompt = (
            "Write eBay listing copy for this new product.\n"
            "Rules: title max 80 characters, natural and descriptive, the product's own brand only if given, "
            "no other brand names, no keyword stuffing, no ALL CAPS, no mention of Amazon or Prime. "
            "overview: 1-2 sentences. bullets: 3-6 short bullets in your own words — do not copy any source "
            "sentence verbatim and do not add claims, warranties or measurements that are not in the source.\n\n"
            + source)
        client = anthropic.Anthropic(api_key=config.env("ANTHROPIC_API_KEY"))
        resp = client.messages.parse(model=st.get("ai_model"), max_tokens=2000,
                                     messages=[{"role": "user", "content": prompt}], output_format=Copy,
                                     output_config={"effort": "low"})
        if resp.stop_reason == "refusal" or resp.parsed_output is None:
            return None
        c = resp.parsed_output
        title = make_title(c.title)  # re-clean + enforce 80 chars
        return title, c.overview.strip(), [b.strip() for b in c.bullets if b.strip()][:6]
    except Exception as exc:
        activity.warning("listed", f"AI listing writer failed for {p.asin}, using built-in writer: {exc}", asin=p.asin)
        return None


def build_listing_content(p: ProductData, with_category: bool = True) -> dict:
    handling = int(st.get("handling_time_days"))
    ai = ai_content(p)
    if ai:
        title, overview, bullets = ai
        description = make_description(p, title, handling, overview, bullets)
    else:
        title = make_title(p.title, p.brand)
        description = make_description(p, title, handling)
    cat_id, cat_name, note = (pick_category(title) if with_category else (None, "", "eBay category is picked once eBay keys are in .env"))
    cat_aspects = None
    if cat_id:
        try:
            from ..ebay import api

            cat_aspects = api.item_aspects(cat_id)
        except Exception as exc:
            note = f"could not load item specifics for category: {exc}"
    aspects, missing = build_aspects(p, cat_aspects)
    return {"title": title, "description_html": description, "aspects": aspects, "missing_required_aspects": missing,
            "category_id": cat_id, "category_name": cat_name, "category_note": note, "images": p.images[:12],
            "writer": "claude" if ai else "built-in"}
