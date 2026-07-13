from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .browser_verify import BrowserVerifier
from .models import Order, OrderResult, OrderStatus
from .pos_driver.base import POSDriver, POSDriverError
from .result_writer import write_results
from .screenshots import capture_screenshot


ProgressCallback = Callable[[str], None]
ResultCallback = Callable[[OrderResult], None]


class OrderEntryWorkflow:
    """Coordinates one batch run across Excel orders, POS actions, and result files."""

    def __init__(
        self,
        driver: POSDriver,
        output_dir: str | Path,
        screenshot_dir: str | Path,
        verifier: BrowserVerifier | None = None,
        logger: logging.Logger | None = None,
        progress_callback: ProgressCallback | None = None,
        result_callback: ResultCallback | None = None,
    ) -> None:
        self.driver = driver
        self.output_dir = Path(output_dir)
        self.screenshot_dir = Path(screenshot_dir)
        self.verifier = verifier
        self.logger = logger or logging.getLogger(__name__)
        self.progress_callback = progress_callback
        self.result_callback = result_callback
        # The UI can pause/resume without killing the worker thread. The driver
        # remains connected, while the workflow waits between order/item steps.
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._stop_event = threading.Event()

    def pause(self) -> None:
        self._pause_event.clear()
        self._emit("已暂停")

    def resume(self) -> None:
        self._pause_event.set()
        self._emit("已继续")

    def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.set()
        self._emit("收到停止请求")

    def run(self, orders: list[Order]) -> list[OrderResult]:
        """Run a batch and persist a result workbook after each completed order."""

        results: list[OrderResult] = []
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._emit(f"准备录入 {len(orders)} 个订单")
        self.driver.connect()
        self.driver.prepare_cashier()

        try:
            for index, order in enumerate(orders, start=1):
                if self._stop_event.is_set():
                    self._emit("任务已停止")
                    break
                self._pause_event.wait()
                result = self._run_one(order, index, len(orders))
                results.append(result)
                if self.result_callback:
                    self.result_callback(result)
                # Persist incrementally so a crash or manual stop still leaves an audit trail.
                write_results(results, self.output_dir)
                if result.status == OrderStatus.FAILED:
                    # Stop on first failure. The operator can inspect the POS,
                    # screenshot, and result row before choosing a retry strategy.
                    self.pause()
                    break
        finally:
            self.driver.close()
        self._emit("任务结束")
        return results

    def _run_one(self, order: Order, index: int, total: int) -> OrderResult:
        result = OrderResult(
            order_no=order.order_no,
            order_date=order.order_date,
            total_received=order.total_received,
            item_count=order.item_count,
            status=OrderStatus.RUNNING,
            started_at=datetime.now(),
        )
        step = "开始"

        def event(message: str) -> None:
            # Keep a per-order event list for the result workbook while also
            # streaming the same message to CLI/UI logs.
            result.events.append(message)
            self._emit(message)

        try:
            event(f"[{index}/{total}] 开始订单 {order.order_no}")
            step = "选择订单日期"
            self.driver.select_order_date(order)
            event(f"已选择日期 {order.order_date.isoformat()}")

            for item in order.items:
                if self._stop_event.is_set():
                    result.status = OrderStatus.SKIPPED
                    result.failed_step = "用户停止"
                    event(f"订单 {order.order_no} 被停止")
                    return self._finish(result)
                self._pause_event.wait()
                step = f"录入条码 {item.barcode}"
                self.driver.enter_item(item)
                event(f"已录入条码 {item.barcode}，数量 {item.quantity}")

            step = "全选商品"
            self.driver.select_all_items()
            event("已全选商品")

            step = "修改订单总额"
            self.driver.change_order_total(order)
            event(f"已修改订单总额 {order.total_received}")

            step = "收银"
            result.print_triggered = self.driver.checkout(order)
            event("已完成收银流程")

            if self.verifier:
                step = "浏览器校验"
                verify_result = self.verifier.verify_order(order)
                result.verified = verify_result.verified
                result.verify_result = verify_result.message
                event(verify_result.message)

            result.status = OrderStatus.SUCCESS
            return self._finish(result)
        except (POSDriverError, Exception) as exc:
            self.logger.exception("订单 %s 在步骤 %s 失败", order.order_no, step)
            result.status = OrderStatus.FAILED
            result.failed_step = step
            result.error = str(exc)
            # Screenshot capture is best-effort; failures here should not hide
            # the original POS automation error.
            result.screenshot_path = capture_screenshot(self.screenshot_dir, order.order_no)
            event(f"订单 {order.order_no} 失败: {step} - {exc}")
            return self._finish(result)

    @staticmethod
    def _finish(result: OrderResult) -> OrderResult:
        result.finished_at = datetime.now()
        return result

    def _emit(self, message: str) -> None:
        self.logger.info(message)
        if self.progress_callback:
            self.progress_callback(message)
