# 系统实现逻辑图

这份文档解释当前代码的整体实现逻辑。主要源码位于：

```text
order_entry_bot/
```

`order_entry_bot` 是 Python 包名，也是项目的主要代码目录。

## 总览

```mermaid
flowchart TD
    User["操作员"] --> UI["桌面 UI\norder_entry_bot/app.py"]
    User --> CLI["命令行 CLI\norder_entry_bot/cli.py"]

    UI --> Reader["Excel 解析\nexcel_reader.py"]
    CLI --> Reader

    Reader --> Orders["订单模型\nmodels.py\nOrder / OrderItem"]
    Orders --> Workflow["录单工作流\nworkflow.py"]

    UI --> Workflow
    CLI --> Workflow

    Workflow --> DriverChoice{"运行模式"}
    DriverChoice -->|Dry-run| DryRun["模拟驱动\ndry_run.py\n不操作 POS"]
    DriverChoice -->|真实运行| WinDriver["Windows POS 驱动\npywinauto_driver.py"]

    WinDriver --> POS["伯俊 POS 客户端"]
    DryRun --> SimLog["模拟步骤日志"]

    Workflow --> Result["结果 Excel\nresult_writer.py"]
    Workflow --> Log["运行日志\nlogger.py"]
    Workflow --> Shot["失败截图\nscreenshots.py"]
    Workflow --> Verify["浏览器校验\nbrowser_verify.py"]

    Tools["控件探测工具\ntools/inspect_pos.py"] --> POS
    Build["Windows 打包脚本\nscripts/build_windows.ps1"] --> Exe["dist/OrderEntryBot.exe"]
```

## 核心流程

```mermaid
sequenceDiagram
    participant Operator as 操作员
    participant UI as UI/CLI
    participant Reader as Excel Reader
    participant Workflow as Workflow
    participant Driver as POS Driver
    participant POS as 伯俊 POS
    participant Output as 日志/结果/截图

    Operator->>UI: 选择订单 Excel，点击开始
    UI->>Reader: 读取 docs/orders.xlsx 或外部 Excel
    Reader-->>UI: 返回 Order 列表和导入摘要
    UI->>Workflow: 启动批量录单
    Workflow->>Driver: connect()
    Driver->>POS: 连接或等待 POS 窗口
    Workflow->>Driver: prepare_cashier()
    Driver->>POS: 登录/进入收银台

    loop 每个订单
        Workflow->>Driver: select_order_date(order)
        Driver->>POS: 选择单据日期
        loop 每个商品
            Workflow->>Driver: enter_item(item)
            Driver->>POS: 粘贴条码并回车
            alt 数量为 1
                Driver->>POS: 保持默认数量
            else 数量大于 1
                Driver->>POS: 定位商品行数量输入框并修改
            end
        end
        Workflow->>Driver: select_all_items()
        Driver->>POS: 全选商品
        Workflow->>Driver: change_order_total(order)
        Driver->>POS: F9/总额折扣，选择特价，输入订单实收
        Workflow->>Driver: checkout(order)
        Driver->>POS: F5 收银，取消会员，回车生成订单
        alt 订单实收为 0
            Driver-->>Workflow: 不触发打印
        else 订单实收非 0
            Driver->>POS: 等待 0.5s 后再次回车调取打印
        end
        Workflow->>Output: 写入 result.xlsx 和日志
    end
```

## 模块职责

| 模块 | 职责 |
| --- | --- |
| `order_entry_bot/app.py` | Tkinter 桌面界面，提供文件选择、预览、开始、暂停、继续、停止 |
| `order_entry_bot/cli.py` | 命令行入口，支持 `preview`、`run`、`save-config` |
| `order_entry_bot/excel_reader.py` | 读取 Excel，按订单号分组商品行，校验字段和金额 |
| `order_entry_bot/models.py` | 定义订单、商品、结果、状态等数据结构 |
| `order_entry_bot/workflow.py` | 批量录单状态机，串联订单步骤、失败处理、暂停/停止 |
| `order_entry_bot/pos_driver/base.py` | POS 驱动接口定义 |
| `order_entry_bot/pos_driver/dry_run.py` | 本地模拟驱动，用于 macOS 或 Windows 上不操作 POS 的流程验证 |
| `order_entry_bot/pos_driver/pywinauto_driver.py` | Windows 真实 POS 自动化驱动 |
| `order_entry_bot/config.py` | 自动化配置、控件文字、fallback 坐标 |
| `order_entry_bot/result_writer.py` | 输出 `outputs/result.xlsx` |
| `order_entry_bot/logger.py` | 输出运行日志 |
| `order_entry_bot/screenshots.py` | 失败时截取整屏 |
| `order_entry_bot/browser_verify.py` | 打开浏览器校验地址，后续补充查询规则 |
| `tools/inspect_pos.py` | 在 Windows 上导出 POS 控件树，辅助校准控件定位 |
| `scripts/build_windows.ps1` | Windows 下安装依赖并打包 `.exe` |

## 为什么使用 `order_entry_bot` 这个目录名

当前目录结构是：

```text
order_entry_bot/
  app.py
  workflow.py
  ...
```

原因：

- `order_entry_bot` 表示 Python 包名，和项目功能对应。
- 打包、导入、命令行入口都依赖包名，例如 `order_entry_bot.cli:main`。
- 这种结构比把所有 `.py` 文件直接放在根目录下更清晰，也更适合后续测试和打包。

## 真实 POS 自动化策略

```mermaid
flowchart LR
    Step["需要操作 POS 控件"] --> TryUIA["优先按控件文字/UI Automation 查找"]
    TryUIA --> Found{"找到控件?"}
    Found -->|是| ClickControl["点击/输入控件"]
    Found -->|否| Fallback["使用配置中的窗口相对坐标"]
    Fallback --> Scaled["按当前 POS 窗口大小缩放"]
    Scaled --> ClickPoint["坐标点击"]
    ClickControl --> Log["记录日志"]
    ClickPoint --> Log
    Log --> Fail{"失败?"}
    Fail -->|是| Screenshot["截图并暂停"]
    Fail -->|否| Next["继续下一步"]
```

这个策略的原因是：录屏显示伯俊 POS 部分控件可识别，但商品表格、全选、数量编辑这类位置可能因 POS 版本或控件实现不同而不稳定。因此真实运行时需要先用 `tools/inspect_pos.py` 导出控件树，再按 Windows 实机情况校准配置。
