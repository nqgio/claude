"""Product-source interface. Swap Amazon for another source by implementing
`ProductProvider` and registering it in `providers/__init__.py`."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field


class ProviderError(Exception):
    """A single request failed (page missing, parse failure...). Safe to skip and continue."""


class SourceBlocked(ProviderError):
    """The source showed a CAPTCHA / block page. All jobs using the source must pause."""


class SourcePaused(ProviderError):
    """The source is in its cooldown window after a block."""


@dataclass
class SearchResult:
    asin: str
    title: str
    price: float | None = None
    rating: float | None = None
    review_count: int | None = None
    prime: bool = False
    sponsored: bool = False
    image: str = ""


@dataclass
class ProductData:
    asin: str
    url: str
    title: str = ""
    brand: str = ""
    price: float | None = None
    in_stock: bool = False
    availability_text: str = ""
    prime: bool = False
    rating: float | None = None
    review_count: int | None = None
    category: str = ""
    images: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    details: dict[str, str] = field(default_factory=dict)
    description: str = ""
    delivery_days: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PurchaseResult:
    ok: bool
    order_id: str = ""
    total_paid: float | None = None
    message: str = ""
    screenshot: str = ""


@dataclass
class TrackingInfo:
    tracking_number: str = ""
    carrier: str = ""
    delivered: bool = False
    status_text: str = ""


class ProductProvider(ABC):
    name = "base"

    @abstractmethod
    def search(self, term: str, category: str | None, page: int) -> list[SearchResult]: ...

    @abstractmethod
    def get_product(self, asin: str) -> ProductData: ...

    def product_url(self, asin: str) -> str:
        return f"https://www.amazon.com/dp/{asin}"

    # Optional order-side capabilities (auto checkout / tracking). Default: unsupported.
    def place_order(self, asin: str, quantity: int, address: dict, guard) -> PurchaseResult:
        return PurchaseResult(ok=False, message=f"{self.name} does not support automatic checkout")

    def get_tracking(self, order_id: str) -> TrackingInfo | None:
        return None

    def open_login_browser(self) -> str:
        return f"{self.name} has no browser login"

    def close(self) -> None:
        pass
