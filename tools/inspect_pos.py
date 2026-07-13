from __future__ import annotations

import argparse
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump Bojun POS UI Automation control tree.")
    parser.add_argument("--title-regex", default=".*伯俊.*BPOS.*|.*伯俊智能BPOS.*", help="POS window title regex")
    parser.add_argument("--output", default="outputs/pos-control-tree.txt", help="Output text path")
    parser.add_argument("--backend", default="uia", choices=["uia", "win32"], help="pywinauto backend")
    args = parser.parse_args()

    try:
        from pywinauto import Desktop
    except Exception as exc:
        raise SystemExit(f"请先在 Windows 环境安装 pywinauto: {exc}")

    pattern = re.compile(args.title_regex)
    windows = Desktop(backend=args.backend).windows()
    matched = [window for window in windows if pattern.match(window.window_text() or "")]
    if not matched:
        print("未找到 POS 窗口。当前窗口：")
        for window in windows:
            print("-", window.window_text())
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    window = matched[0]
    with output_path.open("w", encoding="utf-8") as fh:
        fh.write(f"Window: {window.window_text()}\n")
        fh.write(f"Handle: {window.handle}\n")
        fh.write(f"Backend: {args.backend}\n\n")
        window.print_control_identifiers(file=fh)
    print(f"已输出控件树: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
