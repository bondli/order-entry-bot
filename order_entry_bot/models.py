from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path


class OrderStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class OrderItem:
    barcode: str
    quantity: int
    row_number: int
    size_color: str = ""
    item_received: Decimal | None = None


@dataclass(frozen=True)
class Order:
    order_no: str
    order_date: date
    total_received: Decimal
    expected_item_count: int | None
    payment_method: str
    items: tuple[OrderItem, ...]
    source_first_row: int

    @property
    def requires_print(self) -> bool:
        return self.total_received != Decimal("0")

    @property
    def item_count(self) -> int:
        return len(self.items)


@dataclass
class OrderResult:
    order_no: str
    order_date: date
    total_received: Decimal
    item_count: int
    status: OrderStatus
    started_at: datetime
    finished_at: datetime | None = None
    failed_step: str = ""
    error: str = ""
    screenshot_path: Path | None = None
    print_triggered: bool = False
    verified: bool = False
    verify_result: str = ""
    events: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ImportSummary:
    path: Path
    order_count: int
    item_count: int
    warnings: tuple[str, ...] = ()
