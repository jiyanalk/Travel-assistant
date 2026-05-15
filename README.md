# Travel Assistant

Travel Assistant 是一个轻量化旅游对话助手，使用 `FastAPI WebSocket + Zhipu GLM + Next.js` 构建。

## 项目定位

当前项目只使用 `LightTravelChatAgent` 作为主链路，面向自然语言旅游对话，而不是重型攻略检索或复杂路线规划。

核心能力：

- WebSocket 实时对话
- 结构化旅行需求抽取
- 轻量行程草案生成
- 简单预算估算
- session 级上下文记忆
- preference memory 用户长期偏好记忆

## 后端启动

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements.ai.txt
copy .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

可用接口：

- `GET http://127.0.0.1:8000/health`
- `GET http://127.0.0.1:8000/docs`
- `WS ws://127.0.0.1:8000/ws/trips/{session_id}`

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端默认连接：

```text
ws://localhost:8000/ws/trips/{session_id}
```

## 测试

后端测试：

```bash
.\.venv\Scripts\python.exe -B -m pytest -q
```

前端构建：

```bash
cd frontend
npm run build
```

端到端检查：

```bash
.\.venv\Scripts\python.exe scripts\e2e_light_agent_check.py
```

## 示例输入

```text
我想去成都玩三天，两个人，预算3000，喜欢美食和city walk
我还没想好去哪，想找一个适合周末放松的地方
把刚才的计划改得轻松一点，不要太赶
预算大概1500，两个人，两天，可以怎么玩
我喜欢美食和夜景，下次也记住这个偏好
```

e2e 成功输出：

```text
PASS: 轻量 Agent WebSocket 端到端检查通过。
```
