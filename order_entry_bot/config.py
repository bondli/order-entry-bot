from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RelativePoint:
    """A coordinate captured from a reference recording and scaled to the POS window."""

    x: float
    y: float
    basis_width: int = 2880
    basis_height: int = 1800


@dataclass
class POSAutomationConfig:
    """Tunable settings for the Windows POS driver."""

    window_title_regex: str = ".*伯俊.*BPOS.*|.*伯俊智能BPOS.*"
    startup_timeout_seconds: float = 60.0
    default_timeout_seconds: float = 15.0
    step_delay_seconds: float = 0.2
    print_key_delay_seconds: float = 0.5
    wait_for_manual_print_close: bool = True
    use_clipboard: bool = True
    total_discount_hotkey: str = "{F9}"
    checkout_hotkey: str = "{F5}"
    use_total_discount_hotkey: bool = True
    use_checkout_hotkey: bool = True
    labels: dict[str, list[str]] = field(
        default_factory=lambda: {
            "login": ["登录"],
            "cashier": ["收银台"],
            "date": ["单据日期"],
            "barcode": ["商品搜索"],
            "select_all": ["全选"],
            "total_discount": ["总额折扣"],
            "special_price": ["特价"],
            "discount_confirm": ["确定"],
            "checkout": ["收银"],
            "member_cancel": ["取消"],
        }
    )
    points: dict[str, RelativePoint] = field(
        default_factory=lambda: {
            # Coordinates are based on 2880x1800 recordings and are used only
            # when UI Automation lookup cannot find a stable control.
            "select_all": RelativePoint(38, 378),
            "barcode_input": RelativePoint(320, 1330),
            "special_price_radio": RelativePoint(1028, 396),
            "discount_value_input": RelativePoint(1590, 398),
            "discount_confirm": RelativePoint(1648, 692),
            "member_cancel": RelativePoint(1930, 436),
        }
    )


@dataclass
class AppConfig:
    pos: POSAutomationConfig = field(default_factory=POSAutomationConfig)
    output_dir: str = "outputs"
    screenshot_dir: str = "outputs/screenshots"
    browser_verify_url: str = ""
    dry_run: bool = False
    auto_start_pos: bool = False
    pos_executable_path: str = ""


def load_config(path: str | Path | None = None) -> AppConfig:
    if path is None:
        return AppConfig()
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return app_config_from_dict(data)


def save_default_config(path: str | Path) -> None:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(asdict(AppConfig()), ensure_ascii=False, indent=2), encoding="utf-8")


def app_config_from_dict(data: dict[str, Any]) -> AppConfig:
    """Build typed config objects from JSON loaded by the CLI/UI."""

    pos_data = dict(data.get("pos", {}))
    points = {
        key: RelativePoint(**value) if isinstance(value, dict) else value
        for key, value in pos_data.get("points", {}).items()
    }
    labels = pos_data.get("labels")
    if points:
        pos_data["points"] = points
    if labels is not None:
        pos_data["labels"] = labels
    pos_config = POSAutomationConfig(**pos_data)
    return AppConfig(
        pos=pos_config,
        output_dir=data.get("output_dir", "outputs"),
        screenshot_dir=data.get("screenshot_dir", "outputs/screenshots"),
        browser_verify_url=data.get("browser_verify_url", ""),
        dry_run=bool(data.get("dry_run", False)),
        auto_start_pos=bool(data.get("auto_start_pos", False)),
        pos_executable_path=data.get("pos_executable_path", ""),
    )
