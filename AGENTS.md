# DocPaws — Agent / 贡献者须知

> 改本仓库代码前请先读本文（硬规则）+ 详细约定见架构文档。  
> **Boy scout 规则**：遗留代码允许存在；**你碰到的文件**向规范靠拢，不要扩大偏离。

## 必读文档

| 文档 | 何时读 |
|------|--------|
| [docs/architecture/layering.md](docs/architecture/layering.md) | 不确定代码该放哪一层 |
| [docs/architecture/usecases-style.md](docs/architecture/usecases-style.md) | 改 `backend/docpaws/usecases/` |
| [docs/architecture/config.md](docs/architecture/config.md) | 改 `settings` / `config`、环境变量 |
| [backend/README.md](backend/README.md) | 启动、目录树、检索配置 |

---

## 硬规则（10 条）

### 1. 分层：路由薄、业务在 usecases

- `api/routers/`：鉴权、解析参数、调 usecase、返回统一 JSON/SSE。
- **禁止**在路由里写 SQL、FAISS、复杂业务流程。
- **禁止**在 `usecases/` 里依赖 FastAPI `Request`/`Response`（便于单测、业务不绑 HTTP 上下文）。

### 2. 数据访问进 repo

- 新的 `select(...)` / `session.get` / 复杂查询 → `infra/repos/*`。
- usecases 只做编排（事务边界、调 repo、组合结果）。
- **已知遗留**：`document_service.py`、`kb_service.py` 仍有 inline ORM；**新增代码不要学**，动到旧代码时顺手抽到 repo。（`chat_scope` 已拆至 `scope_repo` + `domain/services/chat_scope`）

### 3. 错误码用常量，前后端对齐

- 后端：`docpaws/api/response.py` 的 `ErrorCode.*`，配合 `AppError(error_code=ErrorCode.xxx, ...)`。
- **禁止**魔法字符串 `"VALIDATION_ERROR"` 等。
- SSE 错误事件的 `code` 字段也用 `ErrorCode`（如 `ErrorCode.RETRIEVAL_FAILED`）
- 前端：`frontend/src/utils/errors.ts` 的 `ErrorCode`；展示用户文案优先 `user_hint`（`getApiErrorHint`）。

### 4. 对外结构用 DTO

- usecases 返回给 api 的数据用 `api/schemas/*` 的 Pydantic 模型，序列化 `XxxData(...).model_dump()`。
- **禁止**在 usecases 里手写大段 response dict。

### 5. usecases 照着模板写

- 新文件或大块重构时，对照 `auth_service.py`、`kb_service.py` 的组织方式（helper 在上、薄 Service 在下）。
- 细节见 [usecases-style.md](docs/architecture/usecases-style.md)。

### 6. 单函数别继续膨胀

- 新逻辑优先拆 `_validate_*` / `_to_*` / 小步骤函数。
- **已知遗留**：`chat_service._stream_answer_events` 过长；**禁止**再往里面塞第 14 步，应按现有 `# 1.`–`# N.` 步骤拆子函数。

### 7. 聊天会话要先落库再拒答

- 空库 / 索引未就绪等可预期失败：**先**创建会话、保存用户消息，再返回提示并写入助手消息（便于历史与续聊）。
- **禁止**在路由层提前 `raise` 挡住整条流式链路（除非无会话语义的全局鉴权）。

### 8. 前端续聊必须带 `conversation_id`

- 弹窗聊天：`useKbModalChat` 在 SSE `meta` / `finished` 绑定 `modalConversationId`，后续请求必须带上。
- **禁止**在 `onScopeRestored`、同步浏览 UI 时误调 `markKbSessionsStale()` 清空会话 id。

### 9. 外部 I/O 走 infra

- 存储 → `infra/storage/*`；向量库 → `infra/vectorstore/*`；任务队列 → `infra/tasks/*`。
- 配置默认值在 `config.py`，环境变量在 `settings.py`；usecases 直接读取，**禁止**在业务层再叠一层 `getattr(..., default)` 兜底。

### 10. 改完跑相关测试

- 后端：`cd backend && python -m pytest`（至少覆盖动到的模块）。
- 动 chat/上传/会话：留意 `tests/test_chat_stream_sse_api.py`、`tests/test_documents_api.py` 等。
- RAG 行为：`eval/run_rag_eval.py`（有改动检索链时再跑）。
- **禁止**在 usecases 风格重构的 commit 里顺手改测试断言；测试因重构坏了，单独 commit 修测试。

---

## 已知偏离（重构中，勿扩大）

| 区域 | 现状 | 目标 |
|------|------|------|
| ~~`chat_scope.py`~~ | ~~纯函数名但内含 ORM~~ | 已拆：`scope_repo` + `domain/services/chat_scope` + usecases 薄层 |
| `document_service.py` | 900+ 行，async/同步混用 | 按域拆分 + 事务说明 |
| `conversation_service` ↔ `chat_service` | citation hydrate 互调 | 抽到共享 helper 或 repo；**选定一种方案做完，不要两种各改一半** |

---

## 提交习惯

- 文档-only：`docs(...)` 单独 commit，不与功能混提。
- 聚焦 diff：一个 commit 解决一类问题（如 `refactor: ErrorCode`、`fix(chat): 续聊`）。
