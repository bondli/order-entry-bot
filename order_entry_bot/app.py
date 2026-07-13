from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .browser_verify import BrowserVerifier
from .config import load_config
from .driver_factory import create_driver
from .excel_reader import OrderExcelError, load_orders
from .logger import setup_logging
from .workflow import OrderEntryWorkflow


class OrderEntryApp(tk.Tk):
    """Small operator UI for previewing Excel files and controlling a batch run."""

    def __init__(self) -> None:
        super().__init__()
        self.title("伯俊 POS 订单自动录入")
        self.geometry("980x680")
        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.workflow: OrderEntryWorkflow | None = None
        self.worker: threading.Thread | None = None

        self.excel_var = tk.StringVar(value=str(Path("docs/orders.xlsx").resolve()) if Path("docs/orders.xlsx").exists() else "")
        self.config_var = tk.StringVar(value="")
        self.output_var = tk.StringVar(value=str(Path("outputs").resolve()))
        self.dry_run_var = tk.BooleanVar(value=True)
        self.verify_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="请选择订单 Excel")

        self._build_ui()
        self.after(100, self._poll_queue)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill=tk.BOTH, expand=True)

        form = ttk.Frame(root)
        form.pack(fill=tk.X)

        self._path_row(form, 0, "订单 Excel", self.excel_var, self._choose_excel)
        self._path_row(form, 1, "配置 JSON", self.config_var, self._choose_config)
        self._path_row(form, 2, "输出目录", self.output_var, self._choose_output_dir)

        options = ttk.Frame(root)
        options.pack(fill=tk.X, pady=(10, 8))
        ttk.Checkbutton(options, text="Dry-run（不操作 POS）", variable=self.dry_run_var).pack(side=tk.LEFT)
        ttk.Checkbutton(options, text="录单后打开浏览器校验", variable=self.verify_var).pack(side=tk.LEFT, padx=(20, 0))

        buttons = ttk.Frame(root)
        buttons.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(buttons, text="预览订单", command=self.preview_orders).pack(side=tk.LEFT)
        ttk.Button(buttons, text="开始", command=self.start).pack(side=tk.LEFT, padx=6)
        ttk.Button(buttons, text="暂停", command=self.pause).pack(side=tk.LEFT, padx=6)
        ttk.Button(buttons, text="继续", command=self.resume).pack(side=tk.LEFT, padx=6)
        ttk.Button(buttons, text="停止", command=self.stop).pack(side=tk.LEFT, padx=6)

        ttk.Label(root, textvariable=self.status_var).pack(fill=tk.X)
        self.log = tk.Text(root, height=18, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        columns = ("order_no", "date", "total", "items", "status", "error")
        self.table = ttk.Treeview(root, columns=columns, show="headings", height=10)
        headings = ("订单号", "日期", "实收", "商品数", "状态", "错误")
        widths = (150, 100, 90, 80, 90, 350)
        for column, heading, width in zip(columns, headings, widths, strict=True):
            self.table.heading(column, text=heading)
            self.table.column(column, width=width, anchor=tk.W)
        self.table.pack(fill=tk.BOTH, expand=False, pady=(8, 0))

    def _path_row(self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar, command) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky=tk.EW, padx=8, pady=4)
        ttk.Button(parent, text="选择", command=command).grid(row=row, column=2, pady=4)
        parent.columnconfigure(1, weight=1)

    def _choose_excel(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xlsm"), ("All files", "*.*")])
        if path:
            self.excel_var.set(path)

    def _choose_config(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if path:
            self.config_var.set(path)

    def _choose_output_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_var.set(path)

    def preview_orders(self) -> None:
        try:
            orders, summary = load_orders(self.excel_var.get())
        except Exception as exc:
            messagebox.showerror("读取失败", str(exc))
            return
        self.table.delete(*self.table.get_children())
        for order in orders:
            self.table.insert("", tk.END, values=(order.order_no, order.order_date, order.total_received, order.item_count, "待录入", ""))
        self._append_log(f"读取成功: {summary.order_count} 个订单，{summary.item_count} 个商品行")
        for warning in summary.warnings:
            self._append_log(f"警告: {warning}")

    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("正在运行", "任务已经在运行")
            return
        self.worker = threading.Thread(target=self._run_worker, daemon=True)
        self.worker.start()

    def pause(self) -> None:
        if self.workflow:
            self.workflow.pause()

    def resume(self) -> None:
        if self.workflow:
            self.workflow.resume()

    def stop(self) -> None:
        if self.workflow:
            self.workflow.stop()

    def _run_worker(self) -> None:
        # Keep automation off the Tk main thread so the UI can remain responsive
        # for pause/stop actions while pywinauto waits on POS controls.
        try:
            config = load_config(self.config_var.get() or None)
            output_dir = Path(self.output_var.get())
            logger, log_path = setup_logging(output_dir)
            orders, _summary = load_orders(self.excel_var.get())
            driver = create_driver(config, dry_run=self.dry_run_var.get())
            verifier = BrowserVerifier(config.browser_verify_url, logger=logger) if self.verify_var.get() else None
            self.workflow = OrderEntryWorkflow(
                driver=driver,
                output_dir=output_dir,
                screenshot_dir=Path(config.screenshot_dir),
                verifier=verifier,
                logger=logger,
                progress_callback=lambda msg: self.queue.put(("log", msg)),
                result_callback=lambda result: self.queue.put(("result", result)),
            )
            self.queue.put(("log", f"日志文件: {log_path}"))
            results = self.workflow.run(orders)
            self.queue.put(("done", f"完成，结果 {len(results)} 条"))
        except OrderExcelError as exc:
            self.queue.put(("error", str(exc)))
        except Exception as exc:
            self.queue.put(("error", f"运行失败: {exc}"))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "result":
                    result = payload
                    self.table.insert(
                        "",
                        tk.END,
                        values=(
                            result.order_no,
                            result.order_date,
                            result.total_received,
                            result.item_count,
                            result.status.value,
                            result.error,
                        ),
                    )
                elif kind == "done":
                    self.status_var.set(str(payload))
                    self._append_log(str(payload))
                elif kind == "error":
                    self.status_var.set(str(payload))
                    messagebox.showerror("错误", str(payload))
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _append_log(self, text: str) -> None:
        self.status_var.set(text)
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)


def main() -> None:
    app = OrderEntryApp()
    app.mainloop()


if __name__ == "__main__":
    main()
