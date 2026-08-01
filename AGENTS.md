# DeepTutor — Agent-Native Architecture

## Overview

DeepTutor is an **agent-native** intelligent learning companion organized
around a two-layer plugin model — single-shot **Tools** invoked by the
LLM, and multi-stage **Capabilities** that take over a turn — exposed
through three entry points: CLI, WebSocket API, and Python SDK.

This fork extends DeepTutor as a **数据标注教学平台** (Data Annotation
Teaching Platform), adding annotation coaching, a task bank with real
datasets, canvas annotation tools, Label Studio integration, and memory
tracking.

## Top-Level Directory Layout

```
├── deeptutor/           # Main Python package (backend core)
├── deeptutor_cli/       # CLI entry points (Typer app)
├── deeptutor_web/       # Pre-packaged Next.js web frontend (wheel)
├── web/                 # Next.js frontend source
├── tests/               # Pytest test suite
├── data/                # Runtime user data (gitignored)
├── assets/              # Static assets
├── scripts/             # Utility scripts
├── requirements/        # Pinned requirements by group
├── packaging/           # Package build configs
├── .github/             # CI/CD workflows
├── compose.yaml         # Podman Compose deployment
├── Dockerfile           # Docker image
├── pyproject.toml       # Project metadata, deps, tool config
├── README.md            # Project-specific README (annotation platform)
├── AGENTS.md            # This file
├── SKILL.md             # Skills system documentation
└── .env.example         # Environment variables template
```

## Architecture

```
Entry Points:  CLI (Typer)  |  WebSocket /api/v1/ws  |  Python SDK
                    ↓                   ↓                   ↓
              ┌─────────────────────────────────────────────────┐
              │              ChatOrchestrator                    │
              │   routes UnifiedContext → selected Capability    │
              │   (defaults to `chat`)                           │
              └──────────┬──────────────┬───────────────────────┘
                         │              │
              ┌──────────▼──┐  ┌────────▼──────────┐
              │ ToolRegistry │  │ CapabilityRegistry │
              │  (Level 1)   │  │   (Level 2)        │
              └──────────────┘  └────────────────────┘
```

All capabilities emit on a shared `StreamBus`; the orchestrator fans
events out to consumers. Runtime settings live in
`data/user/settings/*.json` — project-root `.env` files are intentionally
ignored.

---

## Data Flow (Entry → Response)

```
User Input (CLI arg / WS message / SDK call)
        │
        ▼
[Entry Point] builds TurnRequest
        │
        ▼
DeepTutorApp.start_turn(request)
        │
        ▼
TurnRuntimeManager.start_turn(payload)
  ├── Builds UnifiedContext (context_builder.py)
  │     ├── Loads session conversation history
  │     ├── Resolves tools, knowledge_bases, persona
  │     ├── Injects memory_context, skills_manifest, source_manifest
  │     └── Validates capability config via CAPABILITY_CONFIG_VALIDATORS
  │
  ▼
ChatOrchestrator.handle(context)
  ├── Resolves capability (default: "chat")
  ├── Creates StreamBus, registers in bus registry
  ├── Runs capability.run(context, bus) in asyncio task
  │     │
  │     ▼ (for chat capability)
  │   AgenticChatPipeline.run(context, stream)
  │     ├── Composes system prompt (persona + memory + skills + tools + KB)
  │     ├── Sets up tool schemas (enabled + deferred + auto-mounted)
  │     ├── Creates AgentLoop
  │     └── Runs agentic loop (max 8 rounds):
  │           ├── Each round: 1 LLM call (streams to user)
  │           ├── Tool calls dispatched in parallel
  │           ├── Context window guards (guard_context_window)
  │           ├── ask_user pauses for reply, resumes in-protocol
  │           └── Terminal on no-tool round or tool termination
  │
  ├── Yields ALL StreamEvents to subscriber
  ├── Emits DONE when capability completes
  └── Publishes CAPABILITY_COMPLETE to EventBus
```

---

## Core Layer (`deeptutor/core/`)

### `context.py` — UnifiedContext

The central data object flowing through the system:

| Field | Description |
|-------|-------------|
| `session_id` | Persistent conversation identifier |
| `user_message` | Current user input |
| `conversation_history` | Previous messages (OpenAI format) |
| `enabled_tools` / `allowed_builtin_tools` | Tool gating |
| `active_capability` | Capability name or None for plain chat |
| `knowledge_bases` | KB names for RAG |
| `attachments` | Images/files sent with message |
| `config_overrides` | Per-request config tweaks |
| `language` | UI/response language ("en" \| "zh") |
| `memory_context` | Memory snapshot text → system prompt |
| `persona_context` | Selected persona instructions |
| `skills_manifest` | One-line-per-skill manifest |
| `source_manifest` | One-line-per-source manifest |

### `tool_protocol.py` — Tool Layer Protocol

- **`BaseTool`** (ABC): `get_definition()` → `ToolDefinition`, `execute(**kwargs)` → `ToolResult`
- **`ToolDefinition`**: name, description, parameters (`ToolParameter` list), optional `raw_parameters`
- **`ToolParameter`**: name, type, description, required, default, enum, items
- **`ToolAlias`**: alternative tool name/sub-mode in prompts
- **`ToolPromptHints`**: when-to-use guidance for dynamic prompt assembly
- **`ToolResult`**: content, sources, metadata, success, `terminate_turn`, `pause_for_user`
- **`ToolEventSink`**: async callback for progress streaming

### `capability_protocol.py` — Capability Layer Protocol

- **`CapabilityManifest`**: name, description, stages list, tools_used, cli_aliases, request_schema, config_defaults
- **`BaseCapability`** (ABC): must provide `manifest` + `run(context, stream)`

### `stream.py` / `stream_bus.py` — Event Streaming

**StreamEventType** (Enum): STAGE_START, STAGE_END, THINKING, OBSERVATION, CONTENT,
TOOL_CALL, TOOL_RESULT, PROGRESS, SOURCES, RESULT, ERROR, SESSION, SESSION_META,
DONE, WAIT_FOR_INPUT

**StreamBus**: fan-out async event bus with subscriber pattern, replay,
convenience helpers (`stage()`, `content()`, `thinking()`, `tool_call()`,
`tool_result()`, etc.), `wait_for_input()` for pausing capability execution.
Bus registry (`register_bus`/`unregister_bus`/`get_bus`) manages per-turn buses.

### `events/event_bus.py` — Inter-Module Event Bus

Singleton async event bus with publish/subscribe. Events: SOLVE_COMPLETE,
QUESTION_COMPLETE, CAPABILITY_COMPLETE. Background processor with non-blocking
delivery. Lifecycle: start → process → stop → flush.

### `core/agentic/` — Agentic Engine Primitives

Reusable label-driven LLM loop building blocks:

| Module | Purpose |
|--------|---------|
| `labels.py` | Parse/classify inline XML labels in LLM output |
| `client.py` | OpenAI/Azure client factory with completion kwargs |
| `usage.py` (`UsageTracker`) | Token-usage accumulator across steps |
| `labeled_step.py` | One streaming LLM call with label routing |
| `tool_dispatch.py` | Parallel tool execution with per-tool sub-traces |
| `loop.py` (`run_agentic_loop`) | Label-driven iteration scheduler with `LabelProtocol`, `LoopHost` Protocol |

The **`LoopHost` Protocol** defines callbacks capability hosts implement:
`guard_context_window`, `build_iteration_trace_meta`, `dispatch_tools`,
`resolve_pause`, `emit_terminator`, `emit_final`, `validate_terminal`,
`protocol_retry_notice`, `protocol_repair_message`, `force_finalize`.

### `errors.py` — Error Hierarchy

```
DeepTutorError (base)
├── ConfigurationError
├── ValidationError
├── ServiceError
│   ├── LLMServiceError
│   │   └── LLMContextError
│   └── EnvironmentConfigError
```

### `trace.py` — Trace Helpers

`new_call_id()`, `build_trace_metadata()`, `merge_trace_metadata()`.

---

## Runtime Layer (`deeptutor/runtime/`)

### `orchestrator.py` — ChatOrchestrator

Unified entry: resolves capability name, creates StreamBus, runs capability in
asyncio task, yields events from stream bus, publishes CAPABILITY_COMPLETE.

### `launcher.py` — Web Launcher

Backend (uvicorn) + frontend (Next.js) lifecycle: port detection, conflict
resolution, signal handling, dead-process detection with auto-restart.

### `request_contracts.py` — Request Validation

Pydantic models per capability: `ChatRequestConfig`, `DeepSolveRequestConfig`,
`DeepQuestionRequestConfig`, `VisualizeRequestConfig`. Mapped via
`CAPABILITY_CONFIG_VALIDATORS`.

### `registry/`

| File | Purpose |
|------|---------|
| `capability_registry.py` | Loads built-in + plugin capabilities, singleton |
| `tool_registry.py` | Registers tools, resolves aliases, OpenAI schema gen, prompt via `ToolPromptComposer` |
| `deferred_tools.py` | Progressive disclosure — MCP tools loaded on-demand via `load_tools` |
| `mcp/learner_server.py` | Learner-state MCP **server** (stdio): exposes learning records / radar / skill-tree / task bank / IOU check to external MCP clients via `python -m deeptutor.services.mcp.learner_server` |

### `bootstrap/builtin_capabilities.py`

| Capability | Class Path |
|-----------|------------|
| `chat` | `deeptutor.agents.chat.capability:ChatCapability` |
| `deep_solve` | `deeptutor.capabilities.solve.capability:DeepSolveCapability` |
| `deep_question` | `deeptutor.agents.question.capability:DeepQuestionCapability` |
| `deep_research` | `deeptutor.agents.research.capability:DeepResearchCapability` |
| `math_animator` | `deeptutor.agents.math_animator.capability:MathAnimatorCapability` |
| `visualize` | `deeptutor.agents.visualize.capability:VisualizeCapability` |
| `mastery_path` | `deeptutor.capabilities.mastery.capability:MasteryPathCapability` |

---

## Agents Layer (`deeptutor/agents/`)

### `base_agent.py` — BaseAgent

Unified base for all agents: LLM config management, agent parameters from
`agents.yaml`, prompt loading via `PromptManager`, `call_llm()`/`stream_llm()`,
token tracking (LLMStats), trace callbacks.

### `chat/` — Chat Agent (Default Capability)

- **`capability.py`**: `ChatCapability` — wraps `AgenticChatPipeline`
- **`agentic_pipeline.py`**: `AgenticChatPipeline` — system prompt assembly (persona + memory + skills + KB + tools), tool composition via `ToolMountFlags`, deferred tool management, context window guarding, max 8 rounds
- **`agent_loop.py`**: `AgentLoop` — each round = 1 LLM call (streamed), tool-calling rounds continue, tool-less round = turn ends, `ask_user` pauses for in-protocol reply, inline think tag filtering

### Other Agents

| Agent | Pipeline |
|-------|----------|
| `visualize/` | analyzing → generating → reviewing (SVG/Chart.js/Mermaid/HTML, or Manim via `render_type`) |
| `math_animator/` | concept_analysis → concept_design → code_generation → code_retry → summary → render_output |
| `research/` | rephrasing → decomposing → researching → reporting |
| `question/` | ideation → generation |
| `vision_solver/` | Math image analysis → geometric element detection → GeoGebra commands |

### `_shared/capability_result.py`

`emit_capability_result()` — centralized final emission: response payload +
`cost_summary` from `UsageTracker`.

---

## Capabilities Layer (`deeptutor/capabilities/`)

| Capability | Location | Description |
|------------|----------|-------------|
| `solve/` | Deep Solve | planning → reasoning → writing (RAG, web search, code exec) |
| `mastery/` | Mastery Path | guided learning, spaced repetition, quiz generation, progress tracking |
| `subagent/` | Subagent | tool types for subagent delegation |
| `protocol.py` | - | `LoopCapability`, `KnowledgeCapability` base classes |
| `registry.py` | - | `LOOP_CAPABILITIES` dict, `active_loop_capabilities()` |

---

## Tools Layer (`deeptutor/tools/`)

### User-Toggleable Tools (surface in `/settings/tools`)

| Tool | Class | Description |
|------|-------|-------------|
| `brainstorm` | `BrainstormTool` | Breadth-first idea exploration with rationale |
| `web_search` | `WebSearchTool` | Web search with citations |
| `paper_search` | `PaperSearchToolWrapper` | arXiv preprint search |
| `reason` | `ReasonTool` | Dedicated deep-reasoning LLM call |

### Context-Gated Tools (auto-mounted via `ToolMountFlags`)

| Tool | Condition | Description |
|------|-----------|-------------|
| `rag` | KB attached | Knowledge base retrieval with citations |
| `read_source` | Attachments present | Load attached source full text |
| `read_memory` | Always available | Read user's persistent memory |
| `write_memory` | Always available | Save user preferences to memory |
| `read_skill` | Always available | Load skill playbook on-demand |
| `load_tools` | MCP servers configured | Progressive disclosure loader |
| `exec` | Sandbox available | Shell command execution |
| `code_execution` | Sandbox available | Sandboxed Python/C/C++ execution |
| `list_notebook` | Notebooks exist | List notebooks/records |
| `write_note` | Notebooks exist | Save/edit notebook records |
| `web_fetch` | Always available | Fetch URL as markdown |
| `github` | Always available | Read-only GitHub queries |
| `cron` | Scheduled tasks exist | Cron job management |
| `ask_user` | Always available | Mid-turn clarification (pauses turn) |
| `kb_files` | KB attached | List KB documents |
| `imagegen` / `videogen` | Generation enabled | Media generation |
| `geogebra_analysis` | COMING_SOON | Math image → GeoGebra analysis |

### Tools Location & Registration

All built-in tool wrappers: `deeptutor/tools/builtin/__init__.py`
Installed tool packages: `deeptutor/tools/installed/`
Sub-tools: `deeptutor/tools/subtools/` (MBTI, annotation-tool, etc.)

### Annotation Tools (this fork)

| Tool | Purpose |
|------|---------|
| `AnnotationCheckTool` | Evaluate bbox predictions vs ground truth (IOU/F1/precision/recall) |
| `GetAnnotationTaskTool` | Load annotation tasks from `data/user/workspace/task_bank.json` |
| `LabelStudioCheckTool` | Label Studio import/export validation |
| `LabelStudioCreateProjectTool` | Create Label Studio projects |

---

## Services Layer (`deeptutor/services/`)

### Configuration (`config/`)

| File | Purpose |
|------|---------|
| `runtime_settings.py` | `RuntimeSettingsService` — manages `data/user/settings/*.json` |
| `model_catalog.py` | `ModelCatalogService` — LLM model profile management |
| `loader.py` | Agent parameters from `agents.yaml`, chat params |
| `launch_settings.py` | Backend/frontend port configuration |

**Settings files** under `data/user/settings/`:
- `system.json` — ports, sandbox mode, attachment limits
- `auth.json` — authentication config
- `model_catalog.json` — LLM profiles with provider bindings
- `integrations.json` — PocketBase URL, etc.
- `document_parsing.json` — multi-engine doc parsing config

**Setting priority**: 1. process env vars (overwrites), 2. JSON settings, 3. code defaults.

### LLM Providers (`llm/`)

Client factory with provider routing (cloud vs local). Multi-provider:
OpenAI, Anthropic, DashScope (Alibaba), Perplexity. Feature detection
(`capabilities.py`), context window management (`context_window.py`),
multimodal conversion (`multimodal.py`), telemetry, traffic control.

### Sessions (`session/`)

- **`turn_runtime.py`**: `TurnRuntimeManager` — turn lifecycle (start, subscribe, cancel, regenerate, persist)
- **`context_builder.py`**: builds `UnifiedContext` from request + session state
- **`sqlite_store.py`**: SQLite session persistence
- **`pocketbase_store.py`**: optional PocketBase integration
- **`protocol.py`**: `SessionStoreProtocol` abstract interface

### RAG / Knowledge Base (`rag/`)

Factory pattern with multiple backends: LlamaIndex (default), GraphRAG,
LightRAG. Smart retriever, file routing, index versioning.

### Memory (`memory/`)

Three-layer user memory:
| Layer | Content |
|-------|---------|
| L1 | Trace events (conversation snapshots) |
| L2 | Aggregated summaries |
| L3 | Long-term profile/preferences/scope |

Files: `store.py` (read, write, consolidate), `document.py`, `consolidator/`.

### Personas (`persona/`)

Behaviour/voice presets (teacher, peer, annotation-coach, etc.). Eagerly
injected into system prompt to shape voice from first token. `service.py` +
`presets/` directory.

### Skills (`skill/`)

- **`service.py`**: `SkillService` — CRUD for skill packages (builtin under `deeptutor/skills/builtin/`, user under `data/user/workspace/skills/`)
- **`hub.py`**: external skill hub (ClawHub) integration
- **`taxonomy.py`**: tag management

Skills use `SKILL.md` playbook + optional `references/`. NEVER injected
wholesale; the LLM fetches via `read_skill` tool.

### Partners (`partners/`)

IM-connected companion system:
- `manager.py`: `PartnerManager` — isolated workspace per partner (`data/partners/{id}/`)
- `runtime.py`: `PartnerRunner` — chat-agent-loop driver
- Channel configs: Telegram, WeCom, Lark, DingTalk, Slack, QQ, Matrix, Discord

### Other Services

| Service | Location | Purpose |
|---------|----------|---------|
| Sandbox | `sandbox/` | Code execution (subprocess, bwrap, Docker) |
| Cron | `cron/` | Scheduled task service |
| Notebook | `notebook/` | Record management |
| Search | `search/` | Web search integration |
| Embedding | `embedding/` | Model management |
| Prompt | `prompt/` | `PromptManager` — YAML i18n prompt loading (`{en,zh}`) |
| Subagent | `subagent/` | Spawning and management |
| Doc Parsing | `parsing/` | Multi-engine: MinerU, Docling, MarkItDown, PyMuPDF4LLM |

---

## Learning Engine (`deeptutor/learning/`)

Structured mastery-based learning:
- `models.py` — Pydantic models (KnowledgePoint, LearningModule, QuizAttempt)
- `storage.py` — JSON persistence
- `scheduler.py` — Spaced repetition scheduling
- `mastery.py` — Swappable mastery scoring policy
- `grading.py` — Deterministic answer grading
- `service.py` — Business logic layer
- `prompts/` — LLM prompt templates for quiz/diagnostic generation

---

## Multi-User System (`deeptutor/multi_user/`)

ContextVar-based user isolation:
- `context.py` — user identity context variables
- `identity.py` — user identity resolution
- `grants.py` — permission grants
- Access controls: `knowledge_access.py`, `tool_access.py`, `skill_access.py`, `partner_access.py`, `model_access.py`

---

## API Layer (`deeptutor/api/`)

### `main.py` — FastAPI Application

Lifespan management: LLM init, EventBus start, partners auto-start, cron start,
memory migration. CORS (permissive when no auth, explicit otherwise).

### Routers (`api/routers/`)

| Router | Endpoint | Purpose |
|--------|----------|---------|
| `unified_ws.py` | `/api/v1/ws` | Main WebSocket (turn-based execution) |
| `chat.py` | REST + WS | Lightweight chat |
| `auth.py` | `/api/auth/*` | Login, logout, register, status |
| `knowledge.py` | `/api/kb/*` | Knowledge base CRUD |
| `settings.py` | `/api/settings/*` | Runtime settings |
| `tools.py` | `/api/tools/*` | Tool listing/config |
| `sessions.py` | `/api/sessions/*` | Session management |
| `partners.py` | `/api/partners/*` | Partner management |
| `question.py` | `/api/question/*` | Question generation |
| `memory.py` | `/api/memory/*` | Memory viewing/editing |
| `notebook.py` | `/api/notebook/*` | Notebook CRUD |
| `book.py` | `/api/book/*` | Interactive books |
| `co_writer.py` | `/api/cowriter/*` | Co-writing |
| `skills.py` | `/api/skills/*` | Skill management |
| `personas.py` | `/api/personas/*` | Persona management |
| `subagents.py` | `/api/subagents/*` | Subagent config |
| `agent_config.py` | `/api/agent/*` | Agent configuration |
| `mcp_settings.py` | `/api/mcp/*` | MCP settings |
| `plugins_api.py` | `/api/plugins/*` | Plugin management |
| `system.py` | `/api/system/*` | System info/status |
| `voice.py` | `/api/voice/*` | Voice interaction |
| `mastery_path.py` | `/api/mastery/*` | Learning path |
| `attachments.py` | `/api/attachments/*` | File upload |
| `imports.py` | `/api/imports/*` | Data import |
| `capabilities_settings.py` | `/api/capabilities/*` | Capability settings |
| `question_notebook.py` | `/api/qnotebook/*` | Question notebook |
| `quiz_judge.py` | `/api/quiz-judge/ws` | Quiz AI-judge WebSocket |
| `multi_user/router.py` | `/api/admin/*` | Multi-user management |

---

## CLI Layer (`deeptutor_cli/`)

Typer-based CLI with subcommands:

```bash
deeptutor run <capability> <message>    # Run any capability
deeptutor chat                           # Interactive REPL (/regenerate, /retry)
deeptutor start                          # Backend + frontend
deeptutor serve --port 8001              # API server only
deeptutor partner [list|create|...]      # Partner management
deeptutor kb [list|create|delete|...]    # Knowledge base CRUD
deeptutor skill [list|install|...]       # Skill management
deeptutor config                         # Configuration inspection
deeptutor memory [show|...]              # Memory management
deeptutor notebook [list|...]            # Notebook management
deeptutor session [list|...]             # Session management
deeptutor book [create|...]              # Interactive books
deeptutor provider [login|...]           # OAuth login
```

---

## Skills System (`deeptutor/skills/builtin/`)

Built-in skills shipped with the product:

| Skill | Purpose |
|-------|---------|
| `pdf/` | PDF manipulation |
| `docx/` | Word document operations |
| `pptx/` | PowerPoint creation/editing |
| `xlsx/` | Excel spreadsheet handling |
| `skill-creator/` | Meta-skill for creating new skills |
| `annotation-guide/` | Annotation knowledge (this fork) |

Skills use `SKILL.md` playbook + optional `references/`. They are NEVER
injected wholesale into prompts; the LLM fetches them via `read_skill` tool.

---

## Testing

### Structure

```
tests/
├── conftest.py            # Shared fixtures: StreamBus, UnifiedContext
├── agents/                # Agent-specific tests
├── api/                   # API endpoint tests
├── book/                  # Book engine tests
├── capabilities/          # Capability unit tests
├── cli/                   # CLI tests
├── core/                  # Core protocol tests
├── knowledge/             # KB tests
├── logging/               # Logging tests
├── multi_user/            # Multi-user tests
├── partners/              # Partner system tests
├── runtime/               # Runtime tests
├── scripts/               # Script tests
├── services/              # Service-level tests
├── tools/                 # Tool unit tests
├── utils/                 # Utility tests
└── test_*                 # Top-level integration tests
```

**Tools**: pytest + pytest-asyncio, function-scoped event loop.
Config in `pyproject.toml`: strict markers, short traceback, importlib import mode.

---

## Configuration

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `DEEPTUTOR_HOME` | Runtime workspace root |
| `NEXT_PUBLIC_API_BASE` | API base URL for frontend |
| `BACKEND_PORT` / `FRONTEND_PORT` | Port configuration |
| `TZ` | Time zone |

### Setting Priority

1. Process environment variables (overwrites)
2. `data/user/settings/*.json` files
3. Default values in code

---

## Key Files Reference

| Path | Purpose |
|------|---------|
| `deeptutor/runtime/orchestrator.py` | `ChatOrchestrator` — unified entry |
| `deeptutor/runtime/launcher.py` | Backend + frontend lifecycle / port discovery |
| `deeptutor/runtime/registry/` | Tool + Capability registries |
| `deeptutor/runtime/bootstrap/builtin_capabilities.py` | Built-in capability class paths |
| `deeptutor/services/config/runtime_settings.py` | JSON settings + process-env overrides |
| `deeptutor/core/stream.py`, `stream_bus.py` | StreamEvent protocol + async fan-out |
| `deeptutor/core/tool_protocol.py` | `BaseTool` + `ToolDefinition` + `ToolResult` |
| `deeptutor/core/capability_protocol.py` | `BaseCapability` + `CapabilityManifest` |
| `deeptutor/core/context.py` | `UnifiedContext` dataclass |
| `deeptutor/core/agentic/loop.py` | `run_agentic_loop` — label-driven iteration |
| `deeptutor/core/events/event_bus.py` | Singleton async inter-module event bus |
| `deeptutor/core/errors.py` | Error hierarchy |
| `deeptutor/agents/base_agent.py` | `BaseAgent` — unified agent base |
| `deeptutor/agents/chat/agentic_pipeline.py` | `AgenticChatPipeline` — default chat pipeline |
| `deeptutor/agents/chat/agent_loop.py` | `AgentLoop` — single-loop chat agent |
| `deeptutor/agents/_shared/capability_result.py` | `emit_capability_result()` |
| `deeptutor/tools/builtin/__init__.py` | All built-in tool wrappers |
| `deeptutor/capabilities/` | Built-in capability implementations |
| `deeptutor/services/session/turn_runtime.py` | `TurnRuntimeManager` |
| `deeptutor/services/session/context_builder.py` | `UnifiedContext` construction |
| `deeptutor/services/memory/store.py` | Three-layer memory operations |
| `deeptutor/services/persona/service.py` | Persona management |
| `deeptutor/services/skill/service.py` | Skill CRUD |
| `deeptutor/services/partners/manager.py` | `PartnerManager` |
| `deeptutor/services/prompt/` | `PromptManager` — YAML i18n prompts |
| `deeptutor/app/facade.py` | `DeepTutorApp` — Python SDK facade |
| `deeptutor/api/main.py` | FastAPI application + lifespan |
| `deeptutor/api/routers/unified_ws.py` | Unified WebSocket endpoint |
| `deeptutor/learning/` | Learning engine (mastery, quizzes, scheduling) |
| `deeptutor/multi_user/` | Multi-user isolation + access controls |
| `deeptutor_cli/main.py` | Typer CLI entry point |

---

## Dependency Layers

```
pip install deeptutor      — Full app (CLI + Web/API + packaged Web assets)
pip install deeptutor-cli  — CLI-only (LLM + RAG + providers + document parsing)
pip install -e .           — Source install for development

Source extras (.[ extra ], defined in pyproject.toml):
.[cli]            — CLI-only dependency set
.[server]         — Web/API server dependencies
.[partners]       — Partner channel SDKs + MCP client  (legacy alias: .[tutorbot])
.[matrix]         — Matrix channel for Partners (matrix-nio; needs libolm)
.[matrix-e2e]     — Matrix with end-to-end encryption (matrix-nio[e2e])
.[math-animator]  — Manim addon (powers `visualize` Manim renders + `deeptutor run math_animator`)
.[graphrag]       — GraphRAG backend
.[rag-lightrag]   — LightRAG backend
.[dev]            — Test / lint tooling
.[all]            — Everything above
```

## Key Architectural Concepts

1. **Two-Layer Plugin Model**: Tools (single-shot, LLM-invoked) and Capabilities (multi-stage, turn-owning)
2. **Agent-Native**: Every turn goes through the agentic loop with label-driven LLM protocol
3. **Unified Streaming**: All progress flows through `StreamBus` → subscribers (CLI/WS/SDK)
4. **Context-Gated Tooling**: Tools auto-mount based on `ToolMountFlags` (KB, sandbox, notebooks...)
5. **Progressive Disclosure**: Deferred tools load on-demand via `load_tools` to keep schema surface small
6. **Persona + Skills**: Voice preset (eager, shapes first token) + on-demand knowledge (lazy, via `read_skill`)
7. **Three-Layer Memory**: L1 trace events → L2 aggregated summaries → L3 long-term profile
8. **IM Partner System**: In-process partner runners with channel-specific adapters
9. **Multi-User**: ContextVar-based user isolation with per-user access controls
10. **i18n**: YAML-based prompt templates in `{en,zh}` with `PromptManager`
11. **Deferred Tools**: MCP tools excluded from initial tool list; LLM calls `load_tools` on demand
