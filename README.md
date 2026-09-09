# Operations and Maintenance Testing Tool 1.0

一个用于学习 IT 运维和接口测试的实验项目。

## 功能

- FastAPI `/health` 健康检查接口
- `/ready` 数据库就绪检查（默认 SQLite，也支持 MySQL）
- `/checks` 查询最近的健康检查历史
- `/alerts` 查询最近的告警记录
- `/summary` 查询当前巡检状态摘要
- `/dashboard` 查看监控面板
- PowerShell 自动化健康检查
- 健康检查日志
- 检查失败告警日志
- pytest API 自动化测试
- GitHub 版本管理

## 项目分层

- `app.py`：FastAPI 路由、接口响应和监控页面
- `database.py`：SQLAlchemy 数据库连接、建表、检查记录写入和查询
- `scripts/health_check.ps1`：定时健康检查和告警
- `scripts/register_monitor_task.ps1`：注册 Windows 定时巡检任务
- `scripts/remove_monitor_task.ps1`：删除 Windows 定时巡检任务
- `config/targets.json`：被监控目标及超时时间配置
- `tests/test_api.py`：接口自动化测试

接口层通过 `database.py` 使用数据库。数据库实现通过 SQLAlchemy 统一，默认使用 SQLite，也可以通过环境变量切换到 MySQL，接口层无需改动。

## 查看检查历史

启动服务后访问：

```text
http://127.0.0.1:8000/checks
```

默认返回最近 20 条记录，也可以指定数量：

```text
http://127.0.0.1:8000/checks?limit=5
```

## 查看监控面板

启动服务后访问：

```text
http://127.0.0.1:8000/dashboard
```

页面会展示最新状态和最近 20 条检查记录，每 30 秒自动刷新。
页面还会展示最近的告警记录。

巡检脚本会把当前状态写入 `logs/monitor_status.json`。状态有三种：

- `healthy`：最近一次巡检全部成功
- `unhealthy`：最近一次巡检有失败
- `unknown`：还没有执行过巡检

## 启动服务

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

## 使用环境变量配置

默认服务名是 `ops-test-lab`，默认数据库是项目目录下的 `ops_test.db`。
也可以在启动前临时修改配置：

```powershell
$env:OPS_TEST_SERVICE_NAME = "ops-test-lab-dev"
$env:OPS_TEST_DB_PATH = "ops_test_dev.db"
.\.venv\Scripts\python.exe -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

相对路径会以项目根目录为基准。配置只对当前 PowerShell 窗口生效，关闭窗口后不会永久修改系统环境变量。

数据库访问使用 SQLAlchemy ORM。`OPS_TEST_DATABASE_URL` 优先级高于 `OPS_TEST_DB_PATH`，因此可以通过连接字符串切换数据库。

### 使用本机 MySQL

项目已经支持 MySQL。需要先安装依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

然后在当前 PowerShell 窗口设置连接字符串：

```powershell
$env:OPS_TEST_DATABASE_URL = "mysql+pymysql://ops_app:项目密码@127.0.0.1:3306/ops_test"
```

连接字符串的结构是：

```text
mysql+pymysql://用户名:密码@主机:端口/数据库名
```

其中 `ops_app` 是项目账号，`ops_test` 是项目数据库。真实密码只能保存在本机环境变量中，不要写入代码、README 或 GitHub。

在 MySQL 环境下运行测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

测试会自动创建 `service_checks` 表，并验证接口对数据库的读写。

## 运行自动健康检查

健康检查脚本默认读取 `config/targets.json`，逐个检查配置中的目标：

- `/health`：检查应用服务是否存活
- `/ready`：检查数据库是否就绪

新增监控目标时，只需要编辑 `config/targets.json`，不需要修改 PowerShell 脚本：

```json
{
  "targets": [
    {
      "name": "外部网站示例",
      "url": "https://example.com",
      "timeout_seconds": 5
    }
  ]
}
```

`name` 用于日志和页面识别目标，`url` 是实际检查地址，`timeout_seconds` 是单个目标的超时时间。

运行脚本：

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\health_check.ps1"
$LASTEXITCODE
```

命令行也可以临时覆盖配置文件，用于故障演示或单独检查：

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\health_check.ps1" `
  -TargetUri "http://127.0.0.1:8000/not-found"
```

## 注册 Windows 定时任务

注册一个每 5 分钟运行一次的任务：

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\register_monitor_task.ps1"
```

如果出现“拒绝访问”，请使用“以管理员身份运行”的 Windows PowerShell 再执行注册命令。任务使用当前 Windows 用户、有限权限运行，不需要保存 MySQL 密码。

也可以指定检查间隔，例如每 10 分钟运行一次：

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\register_monitor_task.ps1" -IntervalMinutes 10
```

查看任务状态：

```powershell
Get-ScheduledTask -TaskName "OpsTestLab-Monitor"
Get-ScheduledTaskInfo -TaskName "OpsTestLab-Monitor"
```

手动触发一次任务：

```powershell
Start-ScheduledTask -TaskName "OpsTestLab-Monitor"
```

不再需要时删除任务：

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\remove_monitor_task.ps1"
```

## 可选告警通知

默认情况下，脚本只写入 `logs/alerts.log`。如果配置 `OPS_TEST_ALERT_WEBHOOK_URL`，脚本会在状态从正常变为异常，或从异常恢复为正常时，向该地址发送 JSON 通知。

当前 PowerShell 窗口临时配置示例：

```powershell
$env:OPS_TEST_ALERT_WEBHOOK_URL = "https://你的通知服务地址"
```

默认发送通用 JSON，适合 Webhook.site 等测试接收站。如果使用飞书自定义机器人，额外设置：

```powershell
$env:OPS_TEST_WEBHOOK_PROVIDER = "feishu"
```

飞书机器人接收的是文本消息。首次配置建议使用关键词 `ops-test-lab`，暂时不要选择签名校验；签名校验尚未实现。

通知内容包含：

- `status`：`unhealthy` 或 `recovered`
- `message`：告警说明
- `failed_targets`：失败目标列表
- `checked_at`：UTC 检查时间

通知地址只应保存在本机环境变量中，不要写入代码、README 或 GitHub。没有配置通知地址时，原有日志、退出码和网页功能不受影响。

环境变量只对当前 PowerShell 窗口生效。之后新开的窗口和 Windows 定时任务不会自动继承，需要单独配置运行环境。

如果希望 Windows 定时任务也发送通知，可以复制 `config/local.settings.example.json` 为
`config/local.settings.json`，再把其中的 Webhook 地址替换为真实地址。`config/local.settings.json` 已加入
`.gitignore`，不会被提交到 GitHub。定时任务运行时会自动读取这个本地配置文件。

只有两个接口都返回 HTTP 200 时，退出码才是 `0`；任意一个检查失败，退出码就是 `1`。

如果检查失败，脚本还会在 `logs/alerts.log` 中写入一条 `[ALERT]` 告警记录，并在控制台显示警告。
