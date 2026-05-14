# Travel Assistant

基于 `LangGraph + LangChain + 智谱 GLM + FastAPI WebSocket` 的旅行规划 Agent MVP，可直接启动后端并与前端联调。

## 目录说明

- `app/`: FastAPI 入口、配置和依赖注入
- `api/routes/`: WebSocket 行程会话和用户接口
- `agents/`: Agent 封装层
- `graphs/`: LangGraph 状态机、节点和流程编排
- `services/`: 规则版解析、预算、RAG、Memory、行程生成服务
- `tools/`: 可对接 LangChain Tool 的函数包装
- `schemas/`: Pydantic 数据结构
- `repositories/`、`db/`: SQLite / SQLAlchemy 持久化骨架
- `data/`: 样例 POI、攻略和本地 memory 文件
- `prompts/`: 后续接 LLM 可直接扩展的 Prompt 模板
- `frontend/`: Next.js 最小前端展示骨架

## 快速开始

### 后端

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements.ai.txt
copy .env.example .env
uvicorn app.main:app --reload
```

启动后可访问：

- `http://localhost:8000/health`
- `http://localhost:8000/docs`

如果你只是先把本地后端跑起来并联调前端，安装 `requirements.txt` 就够了。
接入智谱 GLM、LangChain 和向量检索时，再额外安装 `requirements.ai.txt`。

当前已经就绪的联调接口：

- `WS /ws/trips/{session_id}`
- `GET /health`

### 前端

```bash
cd frontend
npm install
npm run dev
```

如果需要显式指定后端地址：

```bash
copy .env.local.example .env.local
npm run dev
```

默认前端会请求 `http://localhost:8000`。
WebSocket 默认会连接 `ws://localhost:8000/ws/trips/{session_id}`。

## 当前实现说明

- 旅行需求解析为本地规则版，便于先跑通框架
- 攻略检索使用本地 Markdown 文本片段
- 预算、路线和行程校验使用规则估算
- `services/llm_service.py` 已预留智谱兼容接入点
- `requirements.txt` 为可启动的核心运行依赖，`requirements.ai.txt` 为后续 AI 扩展依赖
- 缺失信息追问、后续追问和行程修改统一承载在 WebSocket 会话里
- 前端页面已切换为长连接模式，可实时看到节点推进和模型结果
- 后续可逐步替换为真实 GLM 调用、向量检索和地图 API
