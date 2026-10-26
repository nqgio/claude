from app.blocklist import Blocklist, add_terms, parse_csv, seed_if_empty
from app.db import session_scope
from app.models import BlocklistEntry


def test_brand_field_match():
    bl = Blocklist([("Nike", "brand")])
    m = bl.check(brand="NIKE", title="Running shoe")
    assert m and m.field == "brand" and "nike" in m.reason().lower()


def test_title_and_description_match():
    bl = Blocklist([("Yeti", "brand"), ("replica", "keyword")])
    assert bl.check(title="Tumbler compatible with YETI lids").field == "title"
    assert bl.check(description="A high quality replica watch").field == "description"


def test_whole_word_only():
    bl = Blocklist([("Lego", "brand"), ("Coach", "brand")])
    assert bl.check(title="Legolas costume") is None
    assert bl.check(title="Stagecoach model") is None
    assert bl.check(title="Coach whistle") is not None  # whole word → blocked (safe side)


def test_punctuation_and_case_tolerant():
    bl = Blocklist([("Ray-Ban", "brand"), ("Dr. Martens", "brand"), ("Bang & Olufsen", "brand")])
    assert bl.check(title="ray ban style sunglasses")
    assert bl.check(brand="Dr Martens")
    assert bl.check(title="Bang and Olufsen speaker")


def test_no_match():
    assert Blocklist([("Nike", "brand")]).check("Kitchenry", "Garlic press", "steel") is None


def test_seed_and_add():
    n = seed_if_empty()
    assert n > 50
    assert seed_if_empty() == 0
    assert add_terms([("nike", "brand")]) == 0  # duplicate (case-insensitive)
    assert add_terms([("Acme Tools", "brand"), ("bootleg", "keyword")]) == 2
    with session_scope() as s:
        assert s.query(BlocklistEntry).filter_by(term="bootleg", kind="keyword").count() == 1
    bl = Blocklist.load()
    assert bl.check(title="Acme Tools hammer")


def test_csv_import():
    rows = parse_csv("term,kind\nAcme,brand\nbootleg,keyword\n\nZed\n")
    assert rows == [("Acme", "brand"), ("bootleg", "keyword"), ("Zed", "brand")]
