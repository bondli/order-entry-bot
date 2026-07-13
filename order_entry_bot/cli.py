from __future__ import annotations

import argparse
from pathlib import Path

from .browser_verify import BrowserVerifier
from .config import load_config, save_default_config
from .driver_factory import create_driver
from .excel_reader import load_orders
from .logger import setup_logging
from .workflow import OrderEntryWorkflow


def main(argv: list[str] | None = None) -> int:
    """Command line entry point used for preview, dry-run, and real POS runs."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "save-config":
        save_default_config(args.path)
        print(f"已写入默认配置: {args.path}")
        return 0

    if args.command == "preview":
        orders, summary = load_orders(args.excel)
        print(f"Excel: {summary.path}")
        print(f"订单数: {summary.order_count}")
        print(f"商品行数: {summary.item_count}")
        for warning in summary.warnings:
            print(f"警告: {warning}")
        for order in orders:
            print(f"- {order.order_no} {order.order_date.isoformat()} 实收={order.total_received} 商品={order.item_count}")
        return 0

    if args.command == "run":
        config = load_config(args.config)
        output_dir = Path(args.output_dir or config.output_dir)
        logger, log_path = setup_logging(output_dir)
        orders, summary = load_orders(args.excel)
        logger.info("读取 Excel: %s，订单 %s，商品行 %s", summary.path, summary.order_count, summary.item_count)
        for warning in summary.warnings:
            logger.warning(warning)
        driver = create_driver(config, dry_run=args.dry_run)
        verifier = BrowserVerifier(config.browser_verify_url, logger=logger) if args.verify else None
        workflow = OrderEntryWorkflow(
            driver=driver,
            output_dir=output_dir,
            screenshot_dir=Path(config.screenshot_dir),
            verifier=verifier,
            logger=logger,
        )
        results = workflow.run(orders)
        print(f"任务完成，结果数量: {len(results)}")
        print(f"日志: {log_path}")
        print(f"结果表: {output_dir / 'result.xlsx'}")
        return 0

    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="order-entry-bot")
    sub = parser.add_subparsers(dest="command")

    preview = sub.add_parser("preview", help="读取 Excel 并预览待录订单")
    preview.add_argument("excel", help="订单 Excel 路径")

    run = sub.add_parser("run", help="执行录单流程")
    run.add_argument("excel", help="订单 Excel 路径")
    run.add_argument("--config", help="配置 JSON 路径")
    run.add_argument("--output-dir", help="输出目录")
    run.add_argument("--dry-run", action="store_true", help="只跑流程，不操作 POS")
    run.add_argument("--verify", action="store_true", help="录单后打开浏览器校验页面")

    save = sub.add_parser("save-config", help="生成默认配置文件")
    save.add_argument("path", help="配置文件输出路径")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
