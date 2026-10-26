"""Brand / keyword blocklist (VeRO protection)."""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import dataclass

from .db import session_scope
from .models import BlocklistEntry

# Starter list: brands that reseller communities commonly report as filing VeRO
# notices against unauthorized resellers, plus counterfeit-signal keywords.
# It is a starting point, not an authoritative or complete list — review and edit it.
SEED_BRANDS = """
Adidas, Apple, Beats, Bose, Brooks, Burberry, Canada Goose, Cartier, Chanel, Coach, Columbia, Converse, Crocs,
Dior, Disney, Dr. Martens, Dyson, Fendi, Fitbit, Funko, Gucci, GoPro, Hasbro, Hermes, Hydro Flask, Jordan,
Kate Spade, KitchenAid, Le Creuset, Lego, LifeProof, Louis Vuitton, Lululemon, Marvel, Mattel, Michael Kors,
Microsoft, Moncler, Nespresso, New Balance, Nike, Nintendo, North Face, Oakley, OtterBox, Pandora, Patagonia,
Pokemon, Prada, Ralph Lauren, Ray-Ban, Rolex, Samsonite, Skullcandy, Sony, Stanley, Star Wars, Swarovski,
Tiffany, Tommy Hilfiger, Tory Burch, Ugg, Under Armour, Vans, Vera Bradley, Versace, Vitamix, Yeti, Zippo,
Olaplex, Dermalogica, Clinique, Estee Lauder, MAC Cosmetics, Urban Decay, Too Faced, Benefit Cosmetics,
Fenty Beauty, Kylie Cosmetics, Moroccanoil, Paul Mitchell, Revlon, Philips Sonicare, Oral-B, SharkNinja,
Shark, Ninja, Instant Pot, Keurig, Milwaukee, DeWalt, Makita, Snap-on, JBL, Harman Kardon, Bang & Olufsen,
Hot Wheels, Barbie, Peppa Pig, Paw Patrol, Squishmallows, Hello Kitty, Sanrio, NFL, NBA, MLB, NHL
"""
SEED_KEYWORDS = ["replica", "knockoff", "counterfeit", "inspired by", "dupe", "1:1 copy", "aaa quality",
                 "unbranded designer", "fake"]


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
            for name, text in fields:
                if text and pat.search(text):
                    return Match(term, kind, name)
        return None


def seed_if_empty() -> int:
    with session_scope() as s:
        if s.query(BlocklistEntry).count():
            return 0
        brands = [b.strip() for b in SEED_BRANDS.replace("\n", " ").split(",") if b.strip()]
        for b in brands:
            s.add(BlocklistEntry(term=b, kind="brand", source="seed"))
        for k in SEED_KEYWORDS:
            s.add(BlocklistEntry(term=k, kind="keyword", source="seed"))
        return len(brands) + len(SEED_KEYWORDS)


def add_terms(terms: list[tuple[str, str]], source: str = "user") -> int:
    added = 0
    with session_scope() as s:
        existing = {(normalize(e.term), e.kind) for e in s.query(BlocklistEntry).all()}
        for term, kind in terms:
            term, kind = term.strip(), (kind or "brand").strip().lower()
            if kind not in ("brand", "keyword"):
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
