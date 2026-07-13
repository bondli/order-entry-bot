from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from .models import OrderResult


HEADERS = (
    "订单号",
    "订单日期",
    "订单实收",
    "商品数量",
    "状态",
    "失败步骤",
    "失败原因",
    "截图路径",
    "是否已触发打印",
    "是否已校验",
    "校验结果",
    "开始时间",
    "结束时间",
    "事件",
)


def write_results(results: list[OrderResult], output_dir: str | Path) -> Path:
    """Write the latest batch results to an operator-readable Excel file."""

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "result.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "录单结果"
    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for result in results:
        ws.append(
            [
                result.order_no,
                result.order_date.isoformat(),
                float(result.total_received),
                result.item_count,
                result.status.value,
                result.failed_step,
                result.error,
                str(result.screenshot_path or ""),
                "是" if result.print_triggered else "否",
                "是" if result.verified else "否",
                result.verify_result,
                result.started_at.strftime("%Y-%m-%d %H:%M:%S"),
                result.finished_at.strftime("%Y-%m-%d %H:%M:%S") if result.finished_at else "",
                "\n".join(result.events),
            ]
        )

    for column in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in column)
        ws.column_dimensions[column[0].column_letter].width = min(max(max_len + 2, 10), 60)

    wb.save(path)
    return path
