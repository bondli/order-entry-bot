from __future__ import annotations

import logging
import time

from order_entry_bot.models import Order, OrderItem

from .base import POSDriver


class DryRunPOSDriver(POSDriver):
    def __init__(self, delay_seconds: float = 0.02, logger: logging.Logger | None = None) -> None:
        self.delay_seconds = delay_seconds
        self.logger = logger or logging.getLogger(__name__)

    def connect(self) -> None:
        self._log("连接 POS: dry-run")

    def prepare_cashier(self) -> None:
        self._log("进入收银台: dry-run")

    def select_order_date(self, order: Order) -> None:
        self._log("选择订单日期 %s: dry-run", order.order_date.isoformat())

    def enter_item(self, item: OrderItem) -> None:
        self._log("录入条码 %s: dry-run", item.barcode)
        if item.quantity > 1:
            self._log("修改条码 %s 数量为 %s: dry-run", item.barcode, item.quantity)
        else:
            self._log("条码 %s 数量为 1，保持 POS 默认数量: dry-run", item.barcode)

    def select_all_items(self) -> None:
        self._log("全选商品: dry-run")

    def change_order_total(self, order: Order) -> None:
        self._log("选择特价并修改订单总额为 %s: dry-run", order.total_received)

    def checkout(self, order: Order) -> bool:
        self._log("点击收银并取消会员输入: dry-run")
        self._log("第一次回车生成订单: dry-run")
        if not order.requires_print:
            self._log("订单金额为 0，跳过小票打印: dry-run")
            return False
        self._sleep()
        self._log("第二次回车调取小票打印: dry-run")
        return True

    def _log(self, message: str, *args: object) -> None:
        self.logger.info(message, *args)
        self._sleep()

    def _sleep(self) -> None:
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
