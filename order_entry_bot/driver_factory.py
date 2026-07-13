from __future__ import annotations

from .config import AppConfig
from .pos_driver import DryRunPOSDriver, POSDriver
from .pos_driver.pywinauto_driver import PywinautoPOSDriver


def create_driver(config: AppConfig, dry_run: bool = False) -> POSDriver:
    if dry_run or config.dry_run:
        return DryRunPOSDriver()
    return PywinautoPOSDriver(
        config=config.pos,
        executable_path=config.pos_executable_path,
        auto_start=config.auto_start_pos,
    )
