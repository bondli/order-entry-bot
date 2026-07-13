from __future__ import annotations

import logging
import re
import subprocess
import time
from decimal import Decimal
from typing import Any

from order_entry_bot.config import POSAutomationConfig, RelativePoint
from order_entry_bot.models import Order, OrderItem

from .base import POSDriver, POSDriverError

try:
    import pyperclip
    from pywinauto import Application, Desktop, keyboard
except Exception:  # pragma: no cover - exercised on Windows only
    # Non-Windows development machines can still import the package and run
    # dry-run tests. The real driver raises a clear error if used there.
    Application = None
    Desktop = None
    keyboard = None
    pyperclip = None


class PywinautoPOSDriver(POSDriver):
    """Windows POS driver.

    The Bojun POS UI exposes some UI Automation information, but recordings show
    a few controls that are safer to address through configured fallback points.
    This driver therefore tries text/control lookup first and falls back to
    window-relative coordinates where configured.
    """

    def __init__(
        self,
        config: POSAutomationConfig | None = None,
        executable_path: str = "",
        auto_start: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config or POSAutomationConfig()
        self.executable_path = executable_path
        self.auto_start = auto_start
        self.logger = logger or logging.getLogger(__name__)
        self.app: Any = None
        self.window: Any = None

    def connect(self) -> None:
        self._ensure_windows_dependencies()
        if self.auto_start and self.executable_path:
            subprocess.Popen([self.executable_path], shell=False)
        self.window = self._wait_for_window(self.config.startup_timeout_seconds)
        try:
            self.app = Application(backend="uia").connect(handle=self.window.handle)
        except Exception as exc:
            raise POSDriverError(f"连接 POS 窗口失败: {exc}") from exc
        self.window.set_focus()
        self.logger.info("已连接 POS 窗口: %s", self.window.window_text())

    def prepare_cashier(self) -> None:
        self._focus()
        # If login/cashier buttons are present, click them. If already in cashier, these lookups simply no-op.
        self._click_first_label("login", required=False)
        self._click_first_label("cashier", required=False)
        time.sleep(self.config.step_delay_seconds)

    def select_order_date(self, order: Order) -> None:
        self._focus()
        target = order.order_date.strftime("%Y-%m-%d")
        compact = order.order_date.strftime("%Y%m%d")
        if self._click_first_label("date", required=False):
            self._paste_text(target)
            self._press("{ENTER}")
            return
        # Fallback: direct typing can work when the date field keeps focus from previous sessions.
        self.logger.warning("未能定位单据日期控件，尝试直接输入日期 %s", target)
        self._paste_text(target)
        self._press("{ENTER}")
        self.logger.info("已尝试选择订单日期: %s / %s", target, compact)

    def enter_item(self, item: OrderItem) -> None:
        self._focus()
        if not self._click_first_label("barcode", required=False):
            self._click_point("barcode_input", required=False)
        self._paste_text(item.barcode)
        self._press("{ENTER}")
        time.sleep(self.config.step_delay_seconds)
        if item.quantity > 1:
            self._update_item_quantity(item)
        else:
            self.logger.info("条码 %s 数量为 1，保持默认数量", item.barcode)

    def select_all_items(self) -> None:
        self._focus()
        if self._click_first_label("select_all", required=False):
            return
        self._click_point("select_all", required=True)

    def change_order_total(self, order: Order) -> None:
        self._focus()
        # Recordings show F9 opens the "总额折扣" dialog. The label click path is
        # kept as a fallback for POS versions where hotkeys are disabled.
        if self.config.use_total_discount_hotkey:
            self._press(self.config.total_discount_hotkey)
        else:
            if not self._click_first_label("total_discount", required=False):
                self._press(self.config.total_discount_hotkey)
        self._wait_short()
        if not self._click_first_label("special_price", required=False):
            self._click_point("special_price_radio", required=True)
        # After selecting "特价", the amount field is normally focused. If not,
        # click the configured fallback point and paste again.
        if not self._set_focused_edit(format_money(order.total_received)):
            self._click_point("discount_value_input", required=False)
            self._paste_text(format_money(order.total_received))
        if not self._click_first_label("discount_confirm", required=False):
            self._click_point("discount_confirm", required=True)
        self._wait_short()

    def checkout(self, order: Order) -> bool:
        self._focus()
        # F5 is visible on the large "收银" button in the recordings.
        if self.config.use_checkout_hotkey:
            self._press(self.config.checkout_hotkey)
        else:
            if not self._click_first_label("checkout", required=False):
                self._press(self.config.checkout_hotkey)
        self._wait_short()
        if not self._click_first_label("member_cancel", required=False):
            self._click_point("member_cancel", required=False)
        self._wait_short()
        self._press("{ENTER}")
        if not order.requires_print:
            # README-confirmed special case: zero-amount orders finish after the
            # first Enter and should not trigger receipt printing.
            self.logger.info("订单 %s 实收为 0，生成订单后不触发打印", order.order_no)
            return False
        time.sleep(self.config.print_key_delay_seconds)
        self._press("{ENTER}")
        if self.config.wait_for_manual_print_close:
            self.logger.info("已触发打印，请人工关闭 Windows 打印框后继续")
        return True

    def close(self) -> None:
        self.window = None
        self.app = None

    def _update_item_quantity(self, item: OrderItem) -> None:
        # The exact grid editor varies by POS build. Try to find the barcode row text,
        # then tab across to the quantity editor. If that is not available, leave a
        # clear error so Windows calibration can add a coordinate strategy.
        control = self._find_control_by_text(item.barcode, timeout=3)
        if control is None:
            raise POSDriverError(f"无法定位条码 {item.barcode} 所在商品行，不能修改数量")
        try:
            control.click_input()
            self._press("{TAB}")
            self._paste_text(str(item.quantity))
            self._press("{ENTER}")
            self.logger.info("已修改条码 %s 数量为 %s", item.barcode, item.quantity)
        except Exception as exc:
            raise POSDriverError(f"修改条码 {item.barcode} 数量失败: {exc}") from exc

    def _wait_for_window(self, timeout: float) -> Any:
        deadline = time.monotonic() + timeout
        pattern = re.compile(self.config.window_title_regex)
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                for window in Desktop(backend="uia").windows():
                    title = window.window_text() or ""
                    if pattern.match(title):
                        return window
            except Exception as exc:
                last_error = exc
            time.sleep(0.5)
        raise POSDriverError(f"等待 POS 窗口超时: {last_error or self.config.window_title_regex}")

    def _find_control_by_text(self, text: str, timeout: float | None = None) -> Any | None:
        timeout = self.config.default_timeout_seconds if timeout is None else timeout
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                # pywinauto exposes labels, buttons and grid cells through the
                # descendant tree. Text lookup is slower than AutomationId but
                # more practical for this POS while the exact IDs are unknown.
                for control in self.window.descendants():
                    name = control.window_text() or control.element_info.name or ""
                    if text in name:
                        return control
            except Exception:
                pass
            time.sleep(0.2)
        return None

    def _click_first_label(self, key: str, required: bool) -> bool:
        for label in self.config.labels.get(key, []):
            control = self._find_control_by_text(label, timeout=2)
            if control is not None:
                try:
                    control.click_input()
                    self.logger.info("点击控件 %s: %s", key, label)
                    self._wait_short()
                    return True
                except Exception as exc:
                    self.logger.debug("点击控件失败 %s/%s: %s", key, label, exc)
        if required:
            raise POSDriverError(f"无法定位控件: {key}")
        return False

    def _click_point(self, key: str, required: bool) -> bool:
        point = self.config.points.get(key)
        if point is None:
            if required:
                raise POSDriverError(f"缺少坐标配置: {key}")
            return False
        try:
            rect = self.window.rectangle()
            x, y = scale_point(point, rect.width(), rect.height())
            self.window.click_input(coords=(x, y))
            self.logger.info("点击坐标 %s: %s,%s", key, x, y)
            self._wait_short()
            return True
        except Exception as exc:
            if required:
                raise POSDriverError(f"点击坐标 {key} 失败: {exc}") from exc
            self.logger.debug("点击坐标失败 %s: %s", key, exc)
            return False

    def _set_focused_edit(self, text: str) -> bool:
        try:
            self._paste_text(text)
            return True
        except Exception:
            return False

    def _paste_text(self, text: str) -> None:
        if pyperclip is None or keyboard is None:
            raise POSDriverError("pyperclip/pywinauto keyboard 不可用")
        if self.config.use_clipboard:
            pyperclip.copy(text)
            keyboard.send_keys("^v")
        else:
            keyboard.send_keys(text, with_spaces=True)
        self._wait_short()

    def _press(self, keys: str) -> None:
        keyboard.send_keys(keys)
        self._wait_short()

    def _focus(self) -> None:
        if self.window is None:
            raise POSDriverError("尚未连接 POS 窗口")
        try:
            self.window.set_focus()
        except Exception as exc:
            raise POSDriverError(f"无法激活 POS 窗口: {exc}") from exc

    def _wait_short(self) -> None:
        time.sleep(self.config.step_delay_seconds)

    @staticmethod
    def _ensure_windows_dependencies() -> None:
        if Application is None or Desktop is None or keyboard is None:
            raise POSDriverError("pywinauto 驱动只能在安装 pywinauto 的 Windows 环境中运行")


def scale_point(point: RelativePoint, width: int, height: int) -> tuple[int, int]:
    """Scale a recording-based fallback point to the current POS window size."""

    return int(point.x / point.basis_width * width), int(point.y / point.basis_height * height)


def format_money(value: Decimal) -> str:
    return f"{value:.2f}"
