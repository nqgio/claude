from datetime import date
from pathlib import Path

from app.providers import amazon_parser as parser
from app.providers.sample import product_html, search_html
from app.services import carriers
from app.services.content import TITLE_MAX, build_aspects, make_description, make_title, rewrite_feature

FIX = Path(__file__).parent / "fixtures"


def test_parse_sample_product():
    p = parser.parse_product(product_html("B0SAMPLE01", date(2026, 10, 26)), "B0SAMPLE01", today=date(2026, 10, 26))
    assert p.price == 13.99 and p.in_stock and p.prime
    assert p.brand == "Kitchenry" and p.rating == 4.6 and p.review_count == 8412
    assert p.delivery_days == 2
    assert len(p.images) == 3 and p.images[0].startswith("https://")
    assert p.details["Material"] == "Stainless Steel"
    assert "Home & Kitchen" in p.category


def test_parse_alternate_markup():
    html = (FIX / "product_alt.html").read_text()
    p = parser.parse_product(html, "B0ALTALT01", today=date(2026, 10, 26))
    assert p.price == 18.49
    assert p.in_stock and p.prime
    assert p.brand == "ACME"
    assert p.rating == 4.7 and p.review_count == 12345
    assert p.delivery_days == 1
    assert p.details["Item model number"] == "AC-SP5"
    assert p.images == ["https://m.media-amazon.com/images/I/acme-main._AC_SL1500_.jpg"]


def test_out_of_stock_sample():
    p = parser.parse_product(product_html("B0SAMPLE07"), "B0SAMPLE07")
    assert not p.in_stock


def test_parse_search():
    rs = parser.parse_search(search_html("x"))
    assert len(rs) == 12
    r = next(r for r in rs if r.asin == "B0SAMPLE09")
    assert r.review_count == 45 and r.price == 16.99 and r.prime


def test_block_page_detection():
    assert parser.is_block_page("<form action='/errors/validateCaptcha'>Type the characters you see in this image</form>")
    assert parser.is_block_page("", "https://www.amazon.com/errors/validateCaptcha?x=1")
    assert not parser.is_block_page(product_html("B0SAMPLE01"))


def test_tracking_and_order_parsing():
    t = parser.parse_tracking("<div>Shipped with UPS</div><div>Tracking ID: 1Z999AA10123456784</div><h1>Delivered</h1>")
    assert t.tracking_number == "1Z999AA10123456784" and t.carrier == "UPS" and t.delivered
    assert parser.parse_order_total("<table><tr><td>Order total:</td><td>$23.41</td></tr></table>") == 23.41
    assert parser.parse_shipping_cost("<tr><td>Shipping &amp; handling:</td><td>$5.99</td></tr>") == 5.99
    assert parser.parse_shipping_cost("<tr><td>Shipping & handling:</td><td>FREE</td></tr>") == 0.0
    assert parser.parse_order_id("<p>Order # 112-1234567-7654321</p>") == "112-1234567-7654321"


def test_carrier_detection():
    assert carriers.detect("TBA123456789000") == "AMAZON"
    assert carriers.detect("1Z999AA10123456784") == "UPS"
    assert carriers.detect("9400111899223197428490") == "USPS"
    assert carriers.detect("123456789012") == "FEDEX"
    assert carriers.detect("ABC", "Amazon Logistics") == "AMAZON"
    assert carriers.detect("XYZ123") == "OTHER"
    assert carriers.ebay_code("FEDEX") == "FedEx" and carriers.ebay_code("AMAZON") is None


def test_title_cleanup():
    t = make_title("NEW 2026 Upgraded ✨ Amazon's Choice KITCHENRY Garlic Press | Garlic Press | Best Seller, "
                   "Stainless Steel Garlic Mincer Crusher with Silicone Peeler and Cleaning Brush, Dishwasher Safe, Gift for Mom")
    assert len(t) <= TITLE_MAX
    low = t.lower()
    for junk in ("amazon", "best seller", "upgraded", "gift", "✨"):
        assert junk not in low
    assert low.count("garlic press") == 1
    assert "Kitchenry" in t
    assert not t.split()[-1].lower() in ("with", "and", "for")


def test_title_short_and_long():
    assert make_title("Bamboo Spoon") == "Bamboo Spoon"
    long = " ".join(f"Word{i}" for i in range(40))
    assert len(make_title(long)) <= TITLE_MAX


def test_feature_rewrite_is_not_verbatim():
    src = "【HEAT RESISTANT】 Food-grade silicone heads handle up to 600°F. We offer a lifetime warranty, contact us anytime!"
    label, text = rewrite_feature(src)
    assert label == "Heat Resistant"
    assert "warranty" not in text.lower() and "contact" not in text.lower()
    assert text != src


def test_description_and_aspects():
    p = parser.parse_product(product_html("B0SAMPLE01"), "B0SAMPLE01")
    d = make_description(p, "Kitchenry Garlic Press", 1)
    assert "<script" not in d.lower() and "amazon" not in d.lower()
    for f in p.features:
        assert f not in d  # never pasted verbatim
    aspects, missing = build_aspects(p, [
        {"name": "Brand", "required": True, "mode": "FREE_TEXT", "values": ()},
        {"name": "Type", "required": True, "mode": "SELECTION_ONLY", "values": ("Garlic Press", "Peeler")},
        {"name": "Color", "required": False, "mode": "SELECTION_ONLY", "values": ("Silver", "Black")},
        {"name": "Blade Material", "required": True, "mode": "FREE_TEXT", "values": ()},
    ])
    assert aspects["Brand"] == ["Kitchenry"] and aspects["MPN"] == ["KG-GP01"]
    assert aspects["Type"] == ["Garlic Press"] and aspects["Color"] == ["Silver"]
    assert missing == ["Blade Material"]


def test_description_template(fresh_db):
    from app import settings_store as st

    st.update({"description_template": "<div onclick=\"x()\"><h1>{{title}}</h1>{{highlights}}<script>bad()</script>{{img1}}{{nope}}</div>"})
    p = parser.parse_product(product_html("B0SAMPLE01"), "B0SAMPLE01")
    d = make_description(p, "My <Title>", 1)
    assert "<h1>My &lt;Title&gt;</h1>" in d and "<li" in d and "<img src=" in d
    assert "script" not in d and "onclick" not in d and "{{nope}}" in d
