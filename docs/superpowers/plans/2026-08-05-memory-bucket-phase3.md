# 议题①② Phase 3 实现计划：记忆区 API CRUD + 前端管理

> 目标：记忆区 bucket 的管理闭环——后端 `/api/v1/memory/buckets` CRUD 端点 + 前端 Memory 页记忆区管理（列出/创建/查看/删除）。复用已有 `store.read_bucket` / `paths.list_buckets`。

## 现状
- 后端：`store.read_bucket(bucket)` 已有（读 L2/<bucket>/*.md + L3 全局）；`paths.buckets_dir()` / `paths.list_buckets()` 已有；`memory.py` router（`/api/v1/memory`）已有 doc/runs/trace 等，**无 bucket 端点**。
- 前端：`web/components/memory/MemoryHub.tsx`（3 层卡片 + 刷新/设置）；`apiFetch(apiUrl(...))` 模式（`web/lib/api.ts:22,77`）；lucide 图标 + `useTranslation`。
- 测试模式：`tests/api/test_memory_resolver.py`（TestClient + `monkeypatch paths.memory_root` → tmp_path）。

## 后端改动

### 1. `deeptutor/services/memory/store.py` 加 bucket 写操作
- 模块级 `BUCKET_NAME_RE = re.compile(r"^[\w\u4e00-\u9fa5\-]{1,32}$")` 与 `validate_bucket_name(name) -> None`（非法抛 ValueError，防路径穿越：排除 `.`/`/`/`\`/空白/超长）。
- `create_bucket(name) -> bool`：`validate_bucket_name` 后 `buckets_dir()/name.mkdir(parents=True, exist_ok=True)`；返回是否新建（已存在 False）。
- `delete_bucket(name) -> bool`：校验后 `shutil.rmtree(buckets_dir()/name, ignore_errors=True)`，返回目录原是否存在。

### 2. `deeptutor/api/routers/memory.py` 加 4 端点
- `GET  /buckets` → `{"buckets": [{"name": n} for n in paths.list_buckets()]}`（含默认空）
- `POST /buckets`（body `{name}`）→ `store.create_bucket`；已存在 → 409；非法名 → 400
- `GET  /buckets/{name}` → 校验后 `{"name": n, "content": store.read_bucket(n)}`；不存在 → 404
- `DELETE /buckets/{name}` → 校验后删除；不存在 → 404
- 统一 `_validate_bucket(n)` helper：`validate_bucket_name` 失败 → 400，bucket 目录不存在 → 404。

## 前端改动

### 3. 新组件 `web/components/memory/MemoryBuckets.tsx`
- "use client"；`apiFetch(apiUrl("/api/v1/memory/buckets"))` 列 bucket。
- 创建区：文本输入 + 「新建记忆区」按钮 → POST `/buckets`（刷新列表，错误 toast/内联提示）。
- 列表：每区卡片显示名字 + 内容预览（`GET /buckets/{name}` 拉 content，截断展示）；「查看」展开全文（内联 toggle）；「删除」按钮（`window.confirm`）→ DELETE 后刷新。
- 空态文案（"暂无记忆区，创建后可分区隔离标注学习/Python 学习等记忆"）。
- 风格沿用 MemoryHub（`rounded-xl border border-[var(--border)] bg-[var(--card)]`、lucide 图标、`useTranslation`）。

### 4. `web/components/memory/MemoryHub.tsx`
- 在 LayerCard 网格（L3 card 之后）插入 `<MemoryBuckets />`，标题「记忆区（Buckets）」。

## 测试 `tests/api/test_memory_buckets.py`（仿 test_memory_resolver fixture）
1. `test_list_empty` → GET /buckets 返回 `{"buckets": []}`
2. `test_create_and_list` → POST 创建 "标注学习" → GET 列表含它
3. `test_create_duplicate_409`
4. `test_get_bucket_content` → 先写 `L2/标注学习/chat.md` → GET /buckets/标注学习 含 content 且含该文本
5. `test_delete_bucket` → DELETE → GET 列表空；再 DELETE → 404
6. `test_invalid_bucket_name_400` → 名字含 `/`、`..`、空串、超长 → 400

## 验证
- `python -m pytest tests/api/test_memory_buckets.py tests/api/test_memory_resolver.py -v`
- 回归：`python -m pytest tests/services/memory/test_bucket_paths.py tests/services/memory/consolidator/modes/test_bucket_l2.py tests/tools/test_delegate_expert_tool.py -q`
- `ruff check deeptutor/services/memory/store.py deeptutor/api/routers/memory.py`
- 前端：`cd web; npx tsc --noEmit`（忽略 `.next` 预存在损坏文件）；`next build`（若可跑）

## 提交（仅 commit，大版本结束统一 push）
- `feat: 记忆区 API CRUD (/api/v1/memory/buckets) + store create/delete`
- `feat: Memory 页记忆区管理 (列出/创建/查看/删除)`
