# Operations and Maintenance Testing Tool 1.0

一个用于学习 IT 运维和接口测试的实验项目。

## 功能

- FastAPI `/health` 健康检查接口
- `/ready` SQLite 数据库就绪检查
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
- `database.py`：SQLite 连接、建表、检查记录写入和查询
- `scripts/health_check.ps1`：定时健康检查和告警
- `tests/test_api.py`：接口自动化测试

接口层通过 `database.py` 使用数据库。以后切换 MySQL 时，优先替换数据访问层，尽量不修改接口层。

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

## 运行自动健康检查

健康检查脚本默认检查两个接口：

- `/health`：检查应用服务是否存活
- `/ready`：检查数据库是否就绪

运行脚本：

```powershell
powershell.exe -ExecutionPolicy Bypass -File ".\scripts\health_check.ps1"
$LASTEXITCODE
```

只有两个接口都返回 HTTP 200 时，退出码才是 `0`；任意一个检查失败，退出码就是 `1`。

如果检查失败，脚本还会在 `logs/alerts.log` 中写入一条 `[ALERT]` 告警记录，并在控制台显示警告。
