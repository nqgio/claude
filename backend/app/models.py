from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    """Naive UTC timestamp (SQLite has no tz support); the API layer adds the 'Z'."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[object] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    level: Mapped[str] = mapped_column(String(10), default="info", index=True)  # info|warning|error
    category: Mapped[str] = mapped_column(String(30), index=True)
    message: Mapped[str] = mapped_column(Text)
    asin: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    listing_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Product(Base):
    """Cached Amazon product data (one row per ASIN)."""

    __tablename__ = "products"
    asin: Mapped[str] = mapped_column(String(20), primary_key=True)
    source: Mapped[str] = mapped_column(String(30), default="amazon")
    url: Mapped[str] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(Text, default="")
    brand: Mapped[str] = mapped_column(String(200), default="")
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=False)
    availability_text: Mapped[str] = mapped_column(String(200), default="")
    prime: Mapped[bool] = mapped_column(Boolean, default=False)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(String(300), default="")
    images: Mapped[list] = mapped_column(JSON, default=list)
    features: Mapped[list] = mapped_column(JSON, default=list)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    description: Mapped[str] = mapped_column(Text, default="")
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class QueueItem(Base):
    __tablename__ = "queue_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asin: Mapped[str] = mapped_column(String(20), index=True)
    queue_date: Mapped[datetime] = mapped_column(Date, index=True)
    # queued -> scheduled -> posting -> posted | failed ; removed | skipped
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    source: Mapped[str] = mapped_column(String(20), default="auto")  # auto|manual
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # UTC
    title: Mapped[str] = mapped_column(Text, default="")
    amazon_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    ebay_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    preview: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    listing_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asin: Mapped[str] = mapped_column(String(20), index=True)
    amazon_url: Mapped[str] = mapped_column(String(300))
    environment: Mapped[str] = mapped_column(String(12), default="sandbox")
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    sku: Mapped[str] = mapped_column(String(60), index=True)
    offer_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ebay_listing_id: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)
    ebay_category_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ebay_category_name: Mapped[str] = mapped_column(String(300), default="")
    campaign_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ad_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    title: Mapped[str] = mapped_column(String(100))
    description_html: Mapped[str] = mapped_column(Text, default="")
    aspects: Mapped[dict] = mapped_column(JSON, default=dict)
    image_urls: Mapped[list] = mapped_column(JSON, default=list)
    price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    # active | qty0 | ended   (dry_run=True rows are previews that only exist in this app)
    status: Mapped[str] = mapped_column(String(12), default="active", index=True)
    status_reason: Mapped[str] = mapped_column(String(200), default="")
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_reason: Mapped[str] = mapped_column(String(300), default="")
    amazon_price_at_listing: Mapped[float] = mapped_column(Float)
    cost_at_listing: Mapped[float] = mapped_column(Float)  # incl. Amazon sales tax
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)  # breakdown at listing time
    current_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_amazon_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_in_stock: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    expected_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    watchers: Mapped[int] = mapped_column(Integer, default=0)
    last_refreshed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    history: Mapped[list["PriceHistory"]] = relationship(back_populates="listing", cascade="all, delete-orphan")


class PriceHistory(Base):
    __tablename__ = "price_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    amazon_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    ebay_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    in_stock: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    expected_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(String(200), default="")

    listing: Mapped[Listing] = relationship(back_populates="history")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("ebay_order_id", "environment"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ebay_order_id: Mapped[str] = mapped_column(String(40), index=True)
    environment: Mapped[str] = mapped_column(String(12), default="sandbox")
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True)  # eBay order creation (UTC)
    last_modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # awaiting_purchase | purchased | shipped | tracking_uploaded | delivered | cancelled | returned | refunded
    status: Mapped[str] = mapped_column(String(20), default="awaiting_purchase", index=True)
    ebay_fulfillment_status: Mapped[str] = mapped_column(String(30), default="")
    ebay_payment_status: Mapped[str] = mapped_column(String(30), default="")
    flag: Mapped[str] = mapped_column(String(40), default="")  # tba_manual | needs_attention | ...
    flag_reason: Mapped[str] = mapped_column(Text, default="")

    buyer_username: Mapped[str] = mapped_column(String(100), default="")
    ship_name: Mapped[str] = mapped_column(String(200), default="")
    ship_line1: Mapped[str] = mapped_column(String(200), default="")
    ship_line2: Mapped[str] = mapped_column(String(200), default="")
    ship_city: Mapped[str] = mapped_column(String(100), default="")
    ship_state: Mapped[str] = mapped_column(String(50), default="")
    ship_postal: Mapped[str] = mapped_column(String(20), default="")
    ship_country: Mapped[str] = mapped_column(String(5), default="US")
    ship_phone: Mapped[str] = mapped_column(String(40), default="")

    listing_id: Mapped[int | None] = mapped_column(ForeignKey("listings.id", ondelete="SET NULL"), index=True, nullable=True)
    asin: Mapped[str] = mapped_column(String(20), default="")
    title: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    lines: Mapped[list] = mapped_column(JSON, default=list)

    # eBay money (USD)
    item_subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    shipping_charged: Mapped[float] = mapped_column(Float, default=0.0)
    buyer_tax: Mapped[float] = mapped_column(Float, default=0.0)  # collected & remitted by eBay
    revenue_total: Mapped[float] = mapped_column(Float, default=0.0)  # subtotal + shipping + buyer tax

    ebay_fees_est: Mapped[float] = mapped_column(Float, default=0.0)
    promo_fee_est: Mapped[float] = mapped_column(Float, default=0.0)
    ebay_fees_actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    promo_fee_actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refund_to_buyer: Mapped[float] = mapped_column(Float, default=0.0)  # seller-side refund amount
    refund_is_actual: Mapped[bool] = mapped_column(Boolean, default=False)

    # Amazon side
    amazon_url: Mapped[str] = mapped_column(String(300), default="")
    amazon_order_id: Mapped[str] = mapped_column(String(40), default="")
    amazon_cost_est: Mapped[float] = mapped_column(Float, default=0.0)  # current Amazon cost x qty (incl tax)
    amazon_cost: Mapped[float | None] = mapped_column(Float, nullable=True)  # what you actually paid
    amazon_refund: Mapped[float] = mapped_column(Float, default=0.0)
    purchased_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    auto_buy_attempted: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_buy_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    tracking_number: Mapped[str] = mapped_column(String(60), default="")
    carrier: Mapped[str] = mapped_column(String(30), default="")
    tracking_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class BlocklistEntry(Base):
    __tablename__ = "blocklist"
    __table_args__ = (UniqueConstraint("term", "kind"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    term: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(10), default="brand")  # brand|keyword
    source: Mapped[str] = mapped_column(String(10), default="user")  # seed|user|import
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
