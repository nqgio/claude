"""Brand / keyword blocklist (VeRO protection)."""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass

from .db import session_scope
from .models import BlocklistEntry

from . import brand_list

KINDS = ("brand", "brand_exact", "keyword")
SEED_VERSION = 2  # bump when brand_list grows; existing blocklists get the new entries on startup


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = text.lower().replace("’", "'").replace("&", " and ")
    text = re.sub(r"[^a-z0-9']+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _pattern(term: str) -> re.Pattern:
    # Whole-word/phrase match, tolerant of punctuation differences ("Ray-Ban" == "ray ban").
    return re.compile(r"(?<![a-z0-9])" + re.escape(normalize(term)) + r"(?![a-z0-9])")


@dataclass
class Match:
    term: str
    kind: str
    field: str

    def reason(self) -> str:
        return f"blocklisted {self.kind} '{self.term}' found in {self.field}"


class Blocklist:
    def __init__(self, entries: list[tuple[str, str]]):
        self.entries = [(t, k, _pattern(t)) for t, k in entries if normalize(t)]

    @classmethod
    def load(cls) -> "Blocklist":
        with session_scope() as s:
            return cls([(e.term, e.kind) for e in s.query(BlocklistEntry).all()])

    def check(self, brand: str = "", title: str = "", description: str = "") -> Match | None:
        fields = [("brand", normalize(brand)), ("title", normalize(title)), ("description", normalize(description))]
        for term, kind, pat in self.entries:
            # "brand_exact" terms are everyday words (Apple, Shark, Ring): only the product's own brand counts.
            for name, text in (fields[:1] if kind == "brand_exact" else fields):
                if text and pat.search(text):
                    return Match(term, "brand" if kind == "brand_exact" else kind, name)
        return None


def seed_if_empty() -> int:
    """Fill an empty blocklist with the starter list; on an existing one, add what newer versions brought."""
    from . import settings_store as st

    with session_scope() as s:
        empty = s.query(BlocklistEntry).count() == 0
    version = st.get("blocklist_seed_version") or (0 if empty else 1)
    if version >= SEED_VERSION:
        return 0
    n = upgrade_seed(version)
    st.set_internal("blocklist_seed_version", SEED_VERSION)
    return n


def upgrade_seed(from_version: int) -> int:
    """Add starter entries that aren't there yet. Starter brands that are everyday words become exact-brand
    matches (stops "apple slicer" being blocked). Your own entries are never changed, and nothing you removed
    from an older starter list comes back except entries new in this version."""
    added = 0
    exact = {normalize(t) for t, k in brand_list.entries() if k == "brand_exact"}
    with session_scope() as s:
        rows = s.query(BlocklistEntry).all()
        have = {normalize(e.term) for e in rows}
        for e in rows:
            if e.source == "seed" and e.kind == "brand" and normalize(e.term) in exact:
                e.kind = "brand_exact"
        for term, kind in brand_list.entries():
            key = normalize(term)
            if key in have or (from_version >= 1 and key in SEED_V1):
                continue  # already there, or a v1 starter entry you deleted on purpose
            s.add(BlocklistEntry(term=term, kind=kind, source="seed"))
            have.add(key)
            added += 1
    return added


def add_terms(terms: list[tuple[str, str]], source: str = "user") -> int:
    added = 0
    with session_scope() as s:
        existing = {(normalize(e.term), e.kind) for e in s.query(BlocklistEntry).all()}
        for term, kind in terms:
            term, kind = term.strip(), (kind or "brand").strip().lower().replace(" ", "_")
            if kind in ("exact", "brand-exact"):
                kind = "brand_exact"
            if kind not in KINDS:
                kind = "brand"
            key = (normalize(term), kind)
            if not key[0] or key in existing:
                continue
            existing.add(key)
            s.add(BlocklistEntry(term=term, kind=kind, source=source))
            added += 1
    return added


def parse_csv(text: str) -> list[tuple[str, str]]:
    """Accepts 'term' or 'term,kind' rows (header row optional)."""
    rows = []
    for row in csv.reader(io.StringIO(text)):
        if not row or not row[0].strip():
            continue
        term = row[0].strip()
        kind = row[1].strip().lower() if len(row) > 1 else "brand"
        if term.lower() in ("term", "brand", "keyword") and kind in ("kind", "type", "brand", ""):
            continue  # header
        rows.append((term, kind))
    return rows


# The first starter list (v1), so an upgrade doesn't re-add v1 brands you deliberately removed.
SEED_V1 = {normalize(b) for b in """
Adidas, Apple, Beats, Bose, Brooks, Burberry, Canada Goose, Cartier, Chanel, Coach, Columbia, Converse, Crocs,
Dior, Disney, Dr. Martens, Dyson, Fendi, Fitbit, Funko, Gucci, GoPro, Hasbro, Hermes, Hydro Flask, Jordan,
Kate Spade, KitchenAid, Le Creuset, Lego, LifeProof, Louis Vuitton, Lululemon, Marvel, Mattel, Michael Kors,
Microsoft, Moncler, Nespresso, New Balance, Nike, Nintendo, North Face, Oakley, OtterBox, Pandora, Patagonia,
Pokemon, Prada, Ralph Lauren, Ray-Ban, Rolex, Samsonite, Skullcandy, Sony, Stanley, Star Wars, Swarovski,
Tiffany, Tommy Hilfiger, Tory Burch, Ugg, Under Armour, Vans, Vera Bradley, Versace, Vitamix, Yeti, Zippo,
Olaplex, Dermalogica, Clinique, Estee Lauder, MAC Cosmetics, Urban Decay, Too Faced, Benefit Cosmetics,
Fenty Beauty, Kylie Cosmetics, Moroccanoil, Paul Mitchell, Revlon, Philips Sonicare, Oral-B, SharkNinja,
Shark, Ninja, Instant Pot, Keurig, Milwaukee, DeWalt, Makita, Snap-on, JBL, Harman Kardon, Bang & Olufsen,
Hot Wheels, Barbie, Peppa Pig, Paw Patrol, Squishmallows, Hello Kitty, Sanrio, NFL, NBA, MLB, NHL,
replica, knockoff, counterfeit, inspired by, dupe, 1:1 copy, aaa quality, unbranded designer, fake
""".replace("\n", " ").split(",") if b.strip()}
