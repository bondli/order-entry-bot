from __future__ import annotations

import logging
import webbrowser
from dataclasses import dataclass

from .models import Order


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    message: str


class BrowserVerifier:
    def __init__(self, url: str = "", logger: logging.Logger | None = None) -> None:
        self.url = url
        self.logger = logger or logging.getLogger(__name__)

    def verify_order(self, order: Order) -> VerificationResult:
        if not self.url:
            return VerificationResult(False, "未配置浏览器校验地址")
        self.logger.info("打开浏览器校验订单 %s: %s", order.order_no, self.url)
        webbrowser.open(self.url)
        return VerificationResult(False, "已打开浏览器，待人工查询确认")
