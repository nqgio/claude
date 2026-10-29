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


def test_exact_brands_only_match_the_real_brand():
    from app.blocklist import Blocklist

    bl = Blocklist([("Apple", "brand_exact"), ("Ring", "brand_exact"), ("KitchenAid", "brand")])
    assert bl.check("Kitchenry", "Apple Slicer and Corer") is None
    assert bl.check("Generic", "Key Ring Holder") is None
    assert bl.check("Apple", "20W USB-C Power Adapter").term == "Apple"
    assert bl.check("Generic", "Replacement Bowl for KitchenAid Mixer").term == "KitchenAid"


def test_existing_blocklist_upgrades_to_the_full_starter_list():
    from app import blocklist, brand_list
    from app import settings_store as st
    from app.db import session_scope
    from app.models import BlocklistEntry

    with session_scope() as s:  # an older install: v1 starter list, one removed, one of your own
        s.query(BlocklistEntry).delete()
        for t in ["Apple", "Nike", "Shark"]:
            s.add(BlocklistEntry(term=t, kind="brand", source="seed"))
        s.add(BlocklistEntry(term="Acme", kind="brand", source="user"))
    st.set_internal("blocklist_seed_version", 1)
    added = blocklist.seed_if_empty()
    assert added > 500 and st.get("blocklist_seed_version") == blocklist.SEED_VERSION
    with session_scope() as s:
        kinds = {e.term: e.kind for e in s.query(BlocklistEntry)}
    assert kinds["Apple"] == "brand_exact" and kinds["Shark"] == "brand_exact" and kinds["Nike"] == "brand"
    assert kinds["Acme"] == "brand" and "KitchenAid" not in kinds  # deliberately removed v1 entry stays removed
    assert kinds["Cuisinart"] == "brand" and kinds["Ring"] == "brand_exact"
    assert blocklist.seed_if_empty() == 0  # only once
    assert len(brand_list.entries()) > 600
