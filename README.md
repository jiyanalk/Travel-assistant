# LightTravelAgent

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![Agent](https://img.shields.io/badge/Agent-Harness%20%2B%20Tools%20%2B%20Skills-7B61FF)](#核心模块)
[![Eval](https://img.shields.io/badge/Eval-Mock%20%2B%20Live%20Runner-FF6F00)](#评估体系)

一个基于 Agent Harness、模块化工具、Skill、记忆、Trace 与 Eval Harness 构建的轻量化旅游对话助手。

LightTravelAgent 面向旅游对话场景，支持多轮需求收集、结构化信息抽取、轻量行程草案生成、偏好记忆与自动化评估。

## 目录

- [项目概览](#项目概览)
- [核心能力](#核心能力)
- [系统架构](#系统架构)
- [项目结构](#项目结构)
- [核心模块](#核心模块)
- [数据结构](#数据结构)
- [快速开始](#快速开始)
- [WebSocket API](#websocket-api)
- [多轮对话示例](#多轮对话示例)
- [本地 Markdown 知识检索](#本地-markdown-知识检索)
- [评估体系](#评估体系)
- [测试方式](#测试方式)
- [设计原则](#设计原则)
- [简历亮点](#简历亮点)
- [安全边界与限制](#安全边界与限制)

---

## 项目概览

LightTravelAgent 是一个轻量化旅游对话助手。用户可以通过对话逐步补充目的地、旅行天数、人数、预算、兴趣偏好、限制条件和修改需求。

后端会将用户的自然语言旅行需求转换为结构化状态 `LightTripRequest`，生成轻量行程草案 `LightTripPlan`，并通过 `ChatAgentResult` 返回统一的 `assistant_message`。

项目重点不是重型全自动旅行规划系统，而是一个可控、可扩展、可观测、可评估的 Agent 工程架构。当前实现围绕 Agent Harness、确定性工具、模块化 Skill、结构化输出校验、session memory、preference memory、Trace 观察和 Eval Harness 展开。

## 核心能力

- 基于 FastAPI WebSocket 的实时旅游对话
- 多轮旅行需求收集
- 结构化输出：`LightTripRequest`、`LightTripPlan`、`ChatAgentResult`
- Agent Harness 编排上下文、工具、Skill、LLM 调用、校验、fallback 和 Trace
- Tool Registry 管理底层确定性工具
- Skill Registry 管理高层 Agent 能力模块
- session memory 保存当前会话状态
- preference memory 保存长期稳定偏好
- 城市别名标准化，例如：`蓉城 -> 成都`
- 多轮需求合并，例如：先说目的地，再补充人数和预算
- 简单预算估算，不承诺实时价格
- 行程修改提示，例如“改轻松一点”
- 模型输出校验与安全 fallback
- Agent Trace 日志，用于调试和评估
- Eval Harness，默认 mock 模式，可选 live 模式
- 基于本地 Markdown 的关键词检索，为城市上下文提供可控参考

## 系统架构

```text
前端聊天界面
    |
    | WebSocket
    v
/ws/trips/{session_id}
    |
    v
LightTravelChatAgent
    |
    v
AgentHarness
    |
    |-- AgentContext
    |
    |-- ToolRegistry
    |     |-- rag_context_tool
    |     |-- city_alias_tool
    |     |-- trip_request_merge_tool
    |     |-- preference_extractor_tool
    |     |-- simple_budget_tool
    |     |-- trip_quality_check_tool
    |
    |-- SkillRegistry
    |     |-- BudgetSkill
    |     |-- RagContextSkill
    |     |-- PreferenceMemorySkill
    |     |-- PlanRevisionSkill
    |
    |-- Prompt Builder
    |-- LLMService
    |-- OutputValidator
    |-- AgentObserver
    |
    v
ChatAgentResult
    |
    v
assistant_message
```

各层职责：

- **前端聊天界面**：基于 Next.js 和 React，用于发送用户消息，并展示助手回复、解析后的旅行需求和轻量行程草案。
- **WebSocket 路由**：`api/routes/trip_ws.py` 提供 `/ws/trips/{session_id}` 连接，并返回统一的 assistant 事件。
- **LightTravelChatAgent**：WebSocket 与 Agent Harness 之间的轻量入口，负责读取 session 状态、构造 `AgentContext`、调用 Harness 并更新 session。
- **AgentHarness**：核心编排层，统一处理上下文组装、工具执行、Skill 执行、Prompt 构建、LLM 调用、结构化校验、fallback 与 Trace 记录。
- **ToolRegistry**：注册确定性底层工具，例如需求合并、城市别名标准化、预算估算、偏好提取、本地上下文检索和质量检查。
- **SkillRegistry**：注册高层 Agent 能力，例如预算处理、本地上下文检索、偏好记忆和行程修改提示。
- **LLMService**：调用配置好的智谱 GLM 兼容 Chat Completion 接口。
- **OutputValidator**：提取并校验模型输出，确保符合 `ChatAgentResult`。
- **AgentObserver**：将每轮对话 Trace 写入 JSONL，便于调试和评估。
- **ChatAgentResult**：Agent 返回的统一结构化结果。

## 项目结构

```text
Travel-assistant/
├── agents/
│   ├── light_agent_harness.py
│   └── light_travel_chat_agent.py
├── api/
│   └── routes/
│       ├── trip_ws.py
│       └── user.py
├── app/
│   ├── config.py
│   ├── dependencies.py
│   └── main.py
├── schemas/
│   ├── agent_context.py
│   ├── light_trip.py
│   ├── user_profile.py
│   └── ws.py
├── services/
│   ├── agent_observer.py
│   ├── city_alias_service.py
│   ├── light_prompt_builder.py
│   ├── light_rag_service.py
│   ├── llm_service.py
│   ├── memory_service.py
│   ├── output_validator.py
│   ├── preference_extractor_service.py
│   ├── request_merge_service.py
│   ├── retrieval_service.py
│   ├── simple_budget_service.py
│   ├── skill_registry.py
│   ├── tool_registry.py
│   └── ws_session_manager.py
├── skills/
│   ├── base.py
│   ├── budget_skill.py
│   ├── plan_revision_skill.py
│   ├── preference_memory_skill.py
│   └── rag_context_skill.py
├── data/
│   └── knowledge/
│       └── city_guide/
│           ├── beijing.md
│           ├── chengdu.md
│           ├── chongqing.md
│           ├── guangzhou.md
│           ├── shanghai.md
│           └── shenzhen.md
├── evals/
│   ├── README.md
│   ├── light_agent_cases.jsonl
│   └── results/
│       └── latest_eval_result.json
├── scripts/
│   ├── e2e_light_agent_check.py
│   └── eval_light_agent.py
├── frontend/
├── tests/
├── requirements.txt
└── requirements.ai.txt
```

主要目录说明：

- `agents/`：Agent 入口与 Harness 编排逻辑。
- `api/routes/`：FastAPI WebSocket 路由和用户相关路由。
- `app/`：应用初始化、配置、依赖和 FastAPI 入口。
- `schemas/`：Agent 上下文、WebSocket 消息、旅行状态和用户画像相关的 Pydantic 数据结构。
- `services/`：确定性服务、LLM 集成、记忆、检索、校验、Trace 和注册器。
- `skills/`：高层 Agent 能力模块。
- `data/knowledge/city_guide/`：用于关键词检索的本地 Markdown 城市知识。
- `evals/`：JSONL 评估用例、评估说明和最新评估结果。
- `scripts/`：端到端检查脚本和评估运行脚本。
- `frontend/`：Next.js 前端。
- `tests/`：后端单元测试和集成测试。

## 核心模块

### LightTravelChatAgent

`LightTravelChatAgent` 是 WebSocket 路由与 Agent Harness 之间的轻量入口。

它负责：

- 从 `ws_session_manager` 读取 session 状态
- 加载最近对话历史
- 在存在 user id 时加载长期偏好记忆
- 构造 `AgentContext`
- 调用 `AgentHarness`
- 更新 latest request、latest plan 和 message history

### AgentHarness

`AgentHarness` 是核心执行层，负责协调：

- 上下文构造
- LLM 前置 Skill
- 确定性工具
- Prompt 构建
- LLM 调用
- 结构化输出校验
- LLM 后置 Skill
- fallback 兜底
- Trace 记录

### ToolRegistry

`ToolRegistry` 管理底层确定性工具：

- `rag_context_tool`
- `city_alias_tool`
- `trip_request_merge_tool`
- `preference_extractor_tool`
- `simple_budget_tool`
- `trip_quality_check_tool`

工具是小型、确定性的函数，不直接生成最终 assistant message。

### SkillRegistry

`SkillRegistry` 管理高层 Agent 能力：

- `BudgetSkill`
- `RagContextSkill`
- `PreferenceMemorySkill`
- `PlanRevisionSkill`

Skill 可以组合服务或工具，返回结构化上下文或副作用结果，但不直接控制 WebSocket 协议。

### Memory

项目使用两层记忆：

- **Session Memory**：保存当前 WebSocket session 的 latest request、latest plan 和最近消息历史。
- **Preference Memory**：保存稳定的长期用户偏好，例如兴趣、节奏偏好和不喜欢的标签。

Preference memory 会避免保存一次性旅行信息，例如本次目的地、预算、人数和旅行天数。

### OutputValidator

`OutputValidator` 负责提取并校验模型输出，确保结果符合 `ChatAgentResult`。它支持直接 JSON 和常见的 JSON 包裹输出。如果校验失败，Agent 会返回安全 fallback，而不是抛出 WebSocket 500。

### AgentObserver

`AgentObserver` 会将 Trace 记录写入 JSONL。Trace 内容包括 selected tools、selected skills、tool outputs、skill outputs、prompt preview、raw model output、validation status、fallback status、memory updates 和 final intent。

Trace 文件属于本地运行产物，不应提交到仓库。

### Eval Harness

Eval Harness 使用 `evals/light_agent_cases.jsonl` 中的 JSONL 用例。

它支持：

- 默认 mock eval，不调用真实模型
- 通过 `--live` 显式启用真实模型评估
- 对结构化抽取、工具/Skill 调用、记忆、本地上下文检索、fallback 和防幻觉边界进行确定性检查

## 数据结构

### LightTripRequest

```text
origin: Optional[str]
destination: Optional[str]
days: Optional[int]
people: int
budget: Optional[float]
interests: list[str]
travel_style: Optional[str]
constraints: list[str]
```

### LightTripPlan

```text
destination: Optional[str]
days: Optional[int]
summary: str
daily_plan: list[str]
budget_summary: Optional[str]
tips: list[str]
```

### ChatAgentResult

```text
intent: "chat" | "collect_info" | "draft_plan" | "revise_plan" | "budget_estimate"
assistant_message: str
updated_request: Optional[LightTripRequest]
updated_plan: Optional[LightTripPlan]
missing_fields: list[str]
used_tools: list[str]
```

## 快速开始

### 1. 克隆仓库

```powershell
git clone https://github.com/jiyanalk/Travel-assistant.git
cd Travel-assistant
```

### 2. 创建虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 3. 安装后端依赖

```powershell
pip install -r requirements.txt
pip install -r requirements.ai.txt
```

### 4. 配置环境变量

```powershell
copy .env.example .env
```

配置 `.env`：

```env
APP_ENV=development
APP_NAME=travel-planning-agent

ZAI_API_KEY=your_zhipuai_api_key
ZHIPU_MODEL=glm-5.1
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4/

DATABASE_URL=sqlite:///./travel_agent.db
VECTOR_STORE_PATH=./data/vector_store
```

说明：

- `ZAI_API_KEY` 用于 live 模式下的真实模型调用。
- `ZHIPU_MODEL` 和 `ZHIPU_BASE_URL` 用于配置智谱 GLM 兼容 Chat Completion 接口。
- `DATABASE_URL` 用于本地 SQLite 数据层。
- `VECTOR_STORE_PATH` 当前存在于配置中，但当前城市上下文检索是 Markdown 关键词检索，并不是向量数据库检索。
- 不要提交 `.env` 或任何真实 API key。

### 5. 启动后端

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

健康检查：

```text
GET http://127.0.0.1:8000/health
```

预期返回：

```json
{"status":"ok"}
```

### 6. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

前端默认地址：

```text
http://localhost:3000
```

## WebSocket API

WebSocket 地址：

```text
/ws/trips/{session_id}
```

客户端消息示例：

```json
{
  "type": "user_message",
  "user_id": "demo_user",
  "message": "我想去成都玩三天，两个人，预算3000，喜欢美食和city walk"
}
```

其他支持的客户端消息类型：

- `ping`
- `request_snapshot`
- `revise_plan`

服务端 assistant message 示例：

```json
{
  "type": "assistant_message",
  "session_id": "demo_session",
  "message": "...",
  "request": {
    "origin": null,
    "destination": "成都",
    "days": 3,
    "people": 2,
    "budget": 3000,
    "interests": ["美食", "city walk"],
    "travel_style": null,
    "constraints": []
  },
  "plan": {
    "destination": "成都",
    "days": 3,
    "summary": "...",
    "daily_plan": ["...", "...", "..."],
    "budget_summary": "...",
    "tips": ["..."]
  },
  "metadata": {
    "intent": "draft_plan",
    "used_tools": ["rag_context_skill", "budget_skill", "trip_request_merge_tool"]
  }
}
```

## 多轮对话示例

```text
User:
我想去蓉城玩三天

Assistant:
通过城市别名标准化识别 destination=成都，并追问人数、预算或兴趣等缺失信息。

User:
两个人，预算3000，喜欢美食和 city walk

Assistant:
将新信息与上一轮需求合并，生成轻量行程草案，并补充预算摘要。

User:
把计划改轻松一点，不要太赶

Assistant:
根据行程修改提示，给出更轻松的调整版本，减少跨区域移动并保留更多自由时间。

User:
记住我以后喜欢美食和夜景，不喜欢太赶

Assistant:
只保存稳定偏好，不会把本次目的地、预算、人数或天数写入长期记忆。
```

## 本地 Markdown 知识检索

城市知识文件位于：

```text
data/knowledge/city_guide/
```

当前包含城市：

- 北京
- 成都
- 重庆
- 广州
- 上海
- 深圳

检索行为：

- 每个城市一个 Markdown 文件
- 使用关键词匹配和简单打分
- 支持 destination、interests 和 user message keywords
- 当前主检索路径不使用 FAISS、Chroma、Milvus 或其他向量数据库
- 不调用外部搜索 API
- 不承诺实时酒店价格、门票、营业时间或交通信息

## 评估体系

运行 mock eval：

```powershell
.\.venv\Scripts\python.exe scripts\eval_light_agent.py --cases evals\light_agent_cases.jsonl
```

运行 live eval：

```powershell
.\.venv\Scripts\python.exe scripts\eval_light_agent.py --cases evals\light_agent_cases.jsonl --live
```

说明：

- mock 模式是默认模式，不调用真实 LLM。
- `--live` 会显式调用配置好的真实模型。
- 结果会写入 `evals/results/latest_eval_result.json`。
- 当前 eval set 包含 12 个用例。
- 用例覆盖结构化抽取、request merge、城市别名标准化、预算估算、记忆更新、本地上下文检索、防幻觉边界和 fallback。

当前 mock eval 示例：

```json
{
  "total_cases": 12,
  "passed_cases": 12,
  "pass_rate": 1.0,
  "json_valid_rate": 1.0,
  "field_extraction_accuracy": 1.0,
  "tool_or_skill_match_rate": 1.0,
  "memory_update_accuracy": 1.0,
  "rag_hit_rate": 1.0,
  "hallucination_guard_pass_rate": 1.0,
  "fallback_success_rate": 1.0
}
```

这是针对确定性评估用例的 mock 评估结果，不应被理解为真实线上模型准确率。

## 测试方式

后端测试：

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q
```

前端构建：

```powershell
cd frontend
npm run build
```

端到端 WebSocket 检查：

```powershell
.\.venv\Scripts\python.exe scripts\e2e_light_agent_check.py
```

当前测试覆盖：

- `AgentContext`
- `ToolRegistry`
- `SkillRegistry`
- `OutputValidator`
- `AgentObserver`
- `AgentHarness`
- request merge
- preference memory
- city alias normalization
- local Markdown retrieval
- eval harness
- WebSocket e2e

## 设计原则

### Lightweight first

系统定位是轻量化对话助手，而不是重型全自动规划器。

### Deterministic tools before LLM where possible

预算估算、城市别名标准化、需求合并和质量检查等能力优先使用确定性本地工具。

### Structured outputs

模型输出必须先校验为 `ChatAgentResult`，再进入 WebSocket 返回层。

### Memory hygiene

长期记忆只保存稳定偏好，不保存本次目的地、预算、人数、天数等一次性旅行信息。

### Observable and testable

Trace 日志和 eval 用例让系统更容易调试、对比和持续改进。

## 简历亮点

- 构建了基于 FastAPI WebSocket 的旅游对话助手，并配套 Next.js 前端。
- 设计 Agent Harness 编排层，统一处理 Prompt 构建、LLM 调用、工具/Skill 执行、结构化校验、fallback 和 Trace。
- 实现 `ToolRegistry + SkillRegistry`，支持确定性工具与高层 Agent 能力模块化扩展。
- 实现 session memory 和 preference memory，并通过规则避免长期记忆污染。
- 增加 `OutputValidator` 和安全 fallback，避免模型非法输出导致 WebSocket 500。
- 增加 `AgentObserver` JSONL Trace，支持调试和可观测性。
- 搭建 Eval Harness，支持确定性 mock 用例和可选 live 模型评估。

## 安全边界与限制

- 助手不提供实时酒店价格。
- 助手不保证门票实时可用。
- 助手不保证营业时间或实时交通信息。
- 本地 Markdown 检索基于人工维护的城市知识文件，内容可能不完整。
- mock eval 是确定性测试结果，不代表真实线上模型准确率。
- live LLM 效果需要通过 `--live` 单独评估。
