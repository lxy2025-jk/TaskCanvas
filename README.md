# TaskCanvas

TaskCanvas 是一款面向小组协作与个人备考的一体化学习任务管理 Web 应用。

## 项目目标

- 支持用户注册 / 登录、个人学习档案定制
- 支持创建小组、邀请成员、共享任务看板
- 提供任务分类、优先级、截止时间和拖拽排序支持
- 支持考研倒计时、每日任务、错题管理、习惯打卡与智能复盘场景
- 采用前后端分离架构，后端使用 Flask 提供 REST API

## 当前实现

- `work.py`：Flask 后端骨架
- `requirements.txt`：依赖列表
- `index.html`：前端页面样式基础
- `vocab_tool.py`：现有单词复习工具

## 运行方式

1. 创建虚拟环境（如需）：
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. 安装依赖：
   ```powershell
   pip install -r requirements.txt
   ```

3. 启动后端服务：
   ```powershell
   python work.py
   ```

4. 初始化数据库（可选）：
   ```powershell
   curl -X POST http://127.0.0.1:5000/api/init -H "Content-Type: application/json" -d '{"exam_date":"2026-12-31"}'
   ```

## API 参考

- `GET /api/ping`
- `POST /api/init`
- `POST /api/users/register`
- `POST /api/users/login`
- `POST /api/teams`
- `GET /api/teams/:team_id`
- `POST /api/teams/:team_id/invite`
- `POST /api/tasks`
- `GET /api/tasks`
- `PUT /api/tasks/:task_id`
- `DELETE /api/tasks/:task_id`
- `GET /api/countdown`
- `GET /api/dashboard`

## 说明

当前后端实现为项目起步版本，适合作为前端页面、数据库和实时推送功能扩展的基础。
