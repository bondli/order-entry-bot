# Windows 使用和打包指南

这份文档用于把项目移动到 Windows 电脑后安装依赖、验证 Excel、连接伯俊 POS、运行自动录单工具，并最终打包成 `.exe`。

## 1. 安装 Python

推荐安装 Python `3.11` 或 `3.12`。

下载地址：

```text
https://www.python.org/downloads/windows/
```

安装时请勾选：

```text
Add python.exe to PATH
```

安装完成后，在 PowerShell 中检查：

```powershell
python --version
py --version
```

能看到 Python 版本号即可。

## 2. 创建虚拟环境并安装依赖

进入项目目录，例如：

```powershell
cd D:\order-entry-bot
```

创建虚拟环境：

```powershell
py -3.11 -m venv .venv
```

如果 `py -3.11` 不可用，改用：

```powershell
python -m venv .venv
```

激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 提示脚本执行策略不允许，先执行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

然后重新激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

主要依赖说明：

| 依赖 | 用途 |
| --- | --- |
| `openpyxl` | 读取订单 Excel、写结果 Excel |
| `pywinauto` | 操作 Windows 原生伯俊 POS 客户端 |
| `pywin32` | Windows API 支持 |
| `pyperclip` | 使用剪贴板粘贴条码和金额 |
| `pillow` | 失败截图保存 |
| `mss` | 屏幕截图 |

## 3. 验证 Excel 是否能读取

先运行订单预览：

```powershell
python -m order_entry_bot.cli preview docs\orders.xlsx
```

如果正常，会看到类似：

```text
订单数: 4
商品行数: 7
- 20260706004 2026-07-06 实收=243.00 商品=2
```

这一步只读取 Excel，不会操作 POS。

## 4. 先跑 dry-run

dry-run 会跑完整程序流程，但不会操作伯俊 POS。

```powershell
python -m order_entry_bot.cli run docs\orders.xlsx --dry-run --output-dir outputs
```

运行完成后检查：

```text
outputs\logs\
outputs\result.xlsx
```

如果生成了日志和结果表，说明 Excel 解析、工作流、结果输出都正常。

## 5. 探测伯俊 POS 控件

真实自动录单前，需要先确认伯俊 POS 的控件能否被识别。

操作步骤：

1. 打开伯俊 POS 客户端。
2. 登录。
3. 停在主界面或收银台界面。
4. 保持 POS 窗口最大化。
5. 在 PowerShell 中运行下面命令。

UI Automation 探测：

```powershell
python tools\inspect_pos.py --backend uia --output outputs\pos-control-tree-uia.txt
```

Win32 探测：

```powershell
python tools\inspect_pos.py --backend win32 --output outputs\pos-control-tree-win32.txt
```

输出文件：

```text
outputs\pos-control-tree-uia.txt
outputs\pos-control-tree-win32.txt
```

重点检查这些控件是否能在文件中看到：

- 登录按钮
- 收银台入口
- 单据日期
- 商品搜索输入框
- 商品列表中的条码行
- 商品列表中的数量输入框
- 商品列表表头全选
- `总额折扣`
- `特价`
- `确定`
- `收银`
- 会员弹窗 `取消`

如果某些控件无法稳定识别，后续需要改配置中的坐标 fallback。

## 6. 启动桌面工具

运行：

```powershell
python run_app.py
```

界面中建议先这样操作：

1. 选择订单 Excel。
2. 勾选 `Dry-run（不操作 POS）`。
3. 点击 `预览订单`。
4. 点击 `开始`。
5. 确认流程和结果表正常。

确认 dry-run 正常后，再取消 `Dry-run（不操作 POS）`，用真实 POS 和测试订单运行。

## 7. 命令行真实运行

确认伯俊 POS 已登录并可操作后，可以运行：

```powershell
python -m order_entry_bot.cli run docs\orders.xlsx --output-dir outputs
```

注意：这条命令会真实操作 POS。

第一次真实运行建议只放一两单测试订单，确认流程稳定后再批量录入。

## 8. 打包成 exe

在 Windows PowerShell 中运行：

```powershell
.\scripts\build_windows.ps1
```

打包完成后，产物在：

```text
dist\OrderEntryBot\
```

运行：

```text
dist\OrderEntryBot\OrderEntryBot.exe
```

## 9. 真实录单前检查清单

运行正式录单前，请确认：

- 伯俊 POS 已安装。
- 伯俊 POS 可以正常登录。
- POS 窗口最大化。
- Windows 缩放比例固定，例如 `100%` 或 `125%`。
- 测试订单 Excel 可以被程序读取。
- dry-run 已经跑通。
- `tools\inspect_pos.py` 已经输出控件树。
- 日期选择能正确操作。
- 条码能正确录入。
- 数量大于 `1` 的商品能正确修改数量。
- 商品列表表头全选能成功。
- `总额折扣` 弹窗能选择 `特价`。
- 订单实收金额能正确输入。
- `F5` 收银流程正常。
- 会员弹窗 `取消` 正常。
- 非 `0` 元订单会触发打印框。
- `0` 元订单不执行打印后续步骤。
- 失败时能生成日志、截图和结果表。

## 10. 常见问题

### PowerShell 无法激活虚拟环境

执行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

然后重新执行：

```powershell
.\.venv\Scripts\Activate.ps1
```

### 找不到 pywinauto

确认已经激活虚拟环境，并重新安装依赖：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 找不到 POS 窗口

确认：

- 伯俊 POS 已打开。
- POS 标题中包含 `伯俊` 或 `BPOS`。
- POS 没有最小化。
- 以同一个 Windows 用户运行 POS 和自动化程序。

### 控件点击不准

优先确认：

- POS 窗口是否最大化。
- Windows 缩放比例是否和录制/校准时一致。
- 是否需要更新配置文件中的坐标 fallback。

默认 fallback 坐标基于 `docs/` 下 2880x1800 的录屏，程序会按 POS 窗口大小做比例缩放，但真实机器仍可能需要微调。

### 真实运行前想确认不会操作 POS

使用 dry-run：

```powershell
python -m order_entry_bot.cli run docs\orders.xlsx --dry-run --output-dir outputs
```

或者在桌面 UI 中勾选：

```text
Dry-run（不操作 POS）
```
