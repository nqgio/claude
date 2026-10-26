"""Offline sample product source. Renders Amazon-style HTML for a fixed set of
fictional products and runs it through the real Amazon parser, so the whole
pipeline (filters, blocklist, pricing, previews) can be exercised with no network.
Never used unless Settings → Product data source = "Offline sample data"."""
from __future__ import annotations

import html as h
import json
from datetime import date, timedelta

from . import amazon_parser as parser
from .base import ProductData, ProductProvider, ProviderError, PurchaseResult, SearchResult, TrackingInfo

# asin, title, brand, price, rating, reviews, prime, in_stock, ship_days, category, features, details
SAMPLES = [
    ("B0SAMPLE01", "Kitchenry Stainless Steel Garlic Press with Silicone Peeler, Rust Proof, Dishwasher Safe, Easy Squeeze",
     "Kitchenry", 13.99, 4.6, 8412, True, True, 2, ["Home & Kitchen", "Kitchen & Dining", "Kitchen Utensils & Gadgets"],
     ["HEAVY-DUTY BUILD: Made from thick 304 stainless steel that will not rust, bend or break with daily use.",
      "EASY TO CLEAN: Wide hopper and removable basket rinse clean in seconds, dishwasher safe.",
      "BONUS PEELER: Includes a silicone tube peeler that removes skins with a quick roll.",
      "COMFORT GRIP: Long ergonomic handles need less hand strength to crush unpeeled cloves."],
     {"Material": "Stainless Steel", "Color": "Silver", "Item Weight": "10.6 ounces", "Item model number": "KG-GP01",
      "Product Dimensions": "7.5 x 2.4 x 1.6 inches"}),
    ("B0SAMPLE02", "Bamboo Drawer Organizer Set of 5, Expandable Utensil Tray for Kitchen Drawers",
     "HomeNest", 24.49, 4.5, 3120, True, True, 3, ["Home & Kitchen", "Storage & Organization", "Kitchen Storage"],
     ["EXPANDABLE: Adjusts from 13 to 21 inches wide to fit most kitchen drawers.",
      "NATURAL BAMBOO: Sustainable moso bamboo with a smooth water-resistant finish.",
      "5 COMPARTMENTS: Keeps utensils, cutlery and gadgets sorted and visible."],
     {"Material": "Bamboo", "Color": "Natural", "Number of Pieces": "5", "Item model number": "HN-BDO5"}),
    ("B0SAMPLE03", "LED Under Cabinet Lights Motion Sensor, Rechargeable, 3 Pack Wireless Closet Light Bars",
     "BrightWay", 19.99, 4.4, 15230, True, True, 2, ["Tools & Home Improvement", "Lighting & Ceiling Fans", "Under-Cabinet Lights"],
     ["MOTION SENSOR: Turns on automatically when you walk by and off after 20 seconds.",
      "RECHARGEABLE: Built-in battery charges by USB-C and lasts up to 3 months per charge.",
      "STICK ANYWHERE: Magnetic strips mount in seconds with no tools or wiring."],
     {"Color": "White", "Power Source": "Battery Powered", "Number of Items": "3", "Item model number": "BW-UC3"}),
    ("B0SAMPLE04", "YETI Rambler 20 oz Tumbler, Stainless Steel, Vacuum Insulated with MagSlider Lid",
     "YETI", 35.00, 4.8, 42011, True, True, 2, ["Home & Kitchen", "Kitchen & Dining", "Travel & To-Go Drinkware"],
     ["Keeps drinks cold or hot for hours.", "Dishwasher safe."], {"Material": "Stainless Steel", "Color": "Navy"}),
    ("B0SAMPLE05", "Silicone Baking Mat Set of 2, Non-Stick Half Sheet Liners",
     "BakeEase", 9.49, 4.7, 22410, True, True, 2, ["Home & Kitchen", "Bakeware", "Baking Mats"],
     ["NON-STICK: No oil or parchment needed."], {"Material": "Silicone", "Number of Items": "2"}),
    ("B0SAMPLE06", "Cast Iron Skillet Scraper and Chainmail Scrubber Set, Stainless 316L",
     "IronCare", 11.25, 4.7, 5320, True, True, 3, ["Home & Kitchen", "Kitchen & Dining", "Cleaning Brushes"],
     ["2-IN-1 SET: Chainmail scrubber plus polycarbonate pan scraper for stuck-on food.",
      "SAFE ON SEASONING: Cleans cast iron without stripping the seasoning layer.",
      "316L STAINLESS: Hand-linked rings that will not rust or shed."],
     {"Material": "Stainless Steel", "Item model number": "IC-CM2"}),
    ("B0SAMPLE07", "Over the Door Pantry Organizer with 6 Adjustable Baskets", "SpaceLine", 45.99, 4.5, 2210, True,
     False, 5, ["Home & Kitchen", "Storage & Organization"], ["6 adjustable baskets."], {"Material": "Steel"}),
    ("B0SAMPLE08", "Herb Scissors with 5 Blades and Cleaning Comb", "GreenSnip", 12.99, 4.3, 1877, False, True, 9,
     ["Home & Kitchen", "Kitchen Utensils & Gadgets"], ["5 stainless blades."], {"Material": "Stainless Steel"}),
    ("B0SAMPLE09", "Collapsible Silicone Colander Set of 3", "FoldWare", 16.99, 4.6, 45, True, True, 2,
     ["Home & Kitchen", "Colanders & Food Strainers"], ["Folds flat."], {"Material": "Silicone"}),
    ("B0SAMPLE10", "Fresh Herb Keeper Container, Keeps Cilantro, Parsley and Asparagus Fresh for 3 Weeks",
     "GreenSnip", 22.95, 4.5, 6804, True, True, 2, ["Home & Kitchen", "Kitchen Storage", "Food Storage"],
     ["LONGER FRESHNESS: Water reservoir keeps stems hydrated so herbs stay crisp for weeks.",
      "FITS THE FRIDGE DOOR: Slim tall design slides into most refrigerator door shelves.",
      "CLEAR BPA-FREE: See-through body shows when to refresh the water."],
     {"Material": "Plastic", "Color": "Clear", "Item model number": "GS-HK1", "Capacity": "1.5 Liters"}),
    ("B0SAMPLE11", "Over The Sink Dish Drying Rack, 2 Tier Stainless Steel Kitchen Organizer",
     "SpaceLine", 38.99, 4.4, 9120, True, True, 4, ["Home & Kitchen", "Kitchen Storage", "Dish Racks"],
     ["2 TIER STORAGE: Holds plates, bowls, cups and utensils above the sink to free counter space.",
      "ADJUSTABLE WIDTH: Fits sinks from 25 to 33 inches.", "RUST RESISTANT: Powder-coated carbon steel frame."],
     {"Material": "Stainless Steel", "Color": "Black", "Item model number": "SL-OTS2"}),
    ("B0SAMPLE12", "Magnetic Knife Holder for Wall, 16 Inch Stainless Steel Knife Strip",
     "Kitchenry", 17.49, 4.6, 7610, True, True, 2, ["Home & Kitchen", "Kitchen & Dining", "Knife Blocks & Storage"],
     ["STRONG MAGNET: Holds heavy chef knives, scissors and metal tools securely.",
      "EASY INSTALL: Mounting hardware and template included.",
      "SAVES SPACE: Frees up drawers and counters while keeping blades visible."],
     {"Material": "Stainless Steel", "Color": "Silver", "Item model number": "KG-MK16", "Length": "16 inches"}),
]
SAMPLE_BY_ASIN = {s[0]: s for s in SAMPLES}

# Test hook: {asin: {"price": 12.5, "in_stock": False}} to simulate Amazon changes.
OVERRIDES: dict[str, dict] = {}


def product_html(asin: str, today: date | None = None) -> str:
    s = SAMPLE_BY_ASIN.get(asin)
    if not s:
        raise ProviderError(f"{asin}: page not found (404)")
    _, title, brand, price, rating, reviews, prime, in_stock, days, crumbs, features, details = s
    o = OVERRIDES.get(asin, {})
    price, in_stock = o.get("price", price), o.get("in_stock", in_stock)
    deliver = (today or date.today()) + timedelta(days=days)
    imgs = [{"hiRes": f"https://m.media-amazon.com/images/I/{asin}-{i}._AC_SL1500_.jpg"} for i in range(1, 4)]
    rows = "".join(f"<tr><th class='prodDetSectionEntry'>{h.escape(k)}</th><td>{h.escape(v)}</td></tr>" for k, v in details.items())
    return f"""<html><body>
<div id="wayfinding-breadcrumbs_feature_div"><ul>{''.join(f'<li><a>{h.escape(c)}</a></li>' for c in crumbs)}</ul></div>
<span id="productTitle"> {h.escape(title)} </span>
<a id="bylineInfo">Visit the {h.escape(brand)} Store</a>
<span id="acrPopover" title="{rating} out of 5 stars"></span><span id="acrCustomerReviewText">{reviews:,} ratings</span>
<div id="corePrice_feature_div"><span class="a-price"><span class="a-offscreen">${price:.2f}</span></span></div>
{'<i class="a-icon a-icon-prime"></i>' if prime else ''}
<div id="availability"><span>{'In Stock' if in_stock else 'Currently unavailable.'}</span></div>
{'<input id="add-to-cart-button"/><input id="buy-now-button"/>' if in_stock else ''}
<div id="mir-layout-DELIVERY_BLOCK"><span data-csa-c-delivery-time="{deliver:%A, %B} {deliver.day}">FREE delivery</span></div>
<div id="feature-bullets"><ul>{''.join(f'<li><span class="a-list-item">{h.escape(f)}</span></li>' for f in features)}</ul></div>
<table id="productDetails_techSpec_section_1">{rows}</table>
<script>var data = {{'colorImages': {{ 'initial': {json.dumps(imgs)}}}}};</script>
</body></html>"""


def search_html(term: str) -> str:
    cards = []
    for s in SAMPLES:
        asin, title, _, price, rating, reviews, prime = s[:7]
        price = OVERRIDES.get(asin, {}).get("price", price)
        cards.append(f"""<div data-component-type="s-search-result" data-asin="{asin}">
<h2><span>{h.escape(title)}</span></h2><span class="a-price"><span class="a-offscreen">${price:.2f}</span></span>
<span class="a-icon-alt">{rating} out of 5 stars</span><span aria-label="{reviews:,} ratings"></span>
{'<i class="a-icon-prime"></i>' if prime else ''}<img class="s-image" src="https://m.media-amazon.com/images/I/{asin}.jpg"/></div>""")
    return "<html><body>" + "".join(cards) + "</body></html>"


class SampleProvider(ProductProvider):
    name = "sample"

    def search(self, term: str, category: str | None, page: int) -> list[SearchResult]:
        return parser.parse_search(search_html(term)) if page == 1 else []

    def get_product(self, asin: str) -> ProductData:
        return parser.parse_product(product_html(asin), asin, self.product_url(asin))

    def place_order(self, asin, quantity, address, guard) -> PurchaseResult:
        return PurchaseResult(False, message="sample data source cannot place real orders")

    def get_tracking(self, order_id: str) -> TrackingInfo | None:
        return None
