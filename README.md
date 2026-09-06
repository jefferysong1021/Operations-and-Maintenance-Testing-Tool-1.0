# Operations and Maintenance Testing Tool 1.0

一个用于学习 IT 运维和接口测试的实验项目。

## 功能

- FastAPI `/health` 健康检查接口
- `/ready` SQLite 数据库就绪检查
- `/checks` 查询最近的健康检查历史
- PowerShell 自动化健康检查
- 健康检查日志
- pytest API 自动化测试
- GitHub 版本管理

## 查看检查历史

启动服务后访问：

```text
http://127.0.0.1:8000/checks
```

默认返回最近 20 条记录，也可以指定数量：

```text
http://127.0.0.1:8000/checks?limit=5
```

## 启动服务

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```
