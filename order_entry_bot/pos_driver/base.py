from __future__ import annotations

from abc import ABC, abstractmethod

from order_entry_bot.models import Order, OrderItem


class POSDriverError(RuntimeError):
    """Raised when a POS automation step fails."""


class POSDriver(ABC):
    @abstractmethod
    def connect(self) -> None:
        """Connect to, or start, the POS application."""

    @abstractmethod
    def prepare_cashier(self) -> None:
        """Ensure POS is on the cashier/order-entry screen."""

    @abstractmethod
    def select_order_date(self, order: Order) -> None:
        """Select the document date for an order."""

    @abstractmethod
    def enter_item(self, item: OrderItem) -> None:
        """Enter one barcode and update quantity when needed."""

    @abstractmethod
    def select_all_items(self) -> None:
        """Select all entered item rows."""

    @abstractmethod
    def change_order_total(self, order: Order) -> None:
        """Open total discount dialog and set order total."""

    @abstractmethod
    def checkout(self, order: Order) -> bool:
        """Checkout the order. Return True when receipt printing was triggered."""

    def close(self) -> None:
        """Release resources if needed."""
