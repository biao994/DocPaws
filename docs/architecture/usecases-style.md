## usecases 代码风格约定（DocPaws）

> 全栈分层总览见 [layering.md](./layering.md)。

`backend/docpaws/usecases/` 用于「业务编排/用例层」，目标是让路由保持薄、让业务流程集中、让输出格式稳定、方便单测与后续替换 infra 实现。

### 文件结构顺序（统一模板）

同一个文件按如下顺序组织：

1. imports
2. 模块级常量 / 类型别名（可选）
3. **模块级私有 helper**：`_to_*` / `_validate_*` / `_build_*` / `_*_impl`
4. **模块级公开函数**（如果确实需要，例如 `upload_document(...)`）
5. **Service 类**（对外入口，方法尽量薄，只做参数转发/少量编排）

> 原则：helper 在上，Service 在下。读 Service 时不需要跳到底部找实现。

### DTO 序列化（强制）

- usecases 对外返回的结构统一使用 `docpaws/api/schemas/*` 里的 **Pydantic DTO**。
- 序列化统一写法：`XxxData(...).model_dump()`。
- 禁止在 usecases 中手写大段 response dict（除非非常小且一次性，且无复用价值）。

推荐：

- `_to_doc_data(doc) -> dict` 内部只做 `DocumentData(...).model_dump()`
- `_to_*` 命名以资源为中心：`_to_kb_data`、`_to_index_job_data`、`_to_conversation_data`、`_to_feedback_data`

### 错误处理（统一 AppError）

- 业务/可预期错误统一 `raise AppError(...)`，携带：
  - `error_code`（优先使用 `docpaws/api/response.py` 的 `ErrorCode` 常量）
  - `status_code`
  - `message`
  - `details`（可选）
- 禁止在 usecases 中抛 `ValueError("XXX_NOT_FOUND")` 让路由层再翻译。

### 分层边界（必须遵守）

- 允许依赖：`usecases -> domain/models`、`usecases -> infra/*`、`usecases -> api/schemas`、`usecases -> errors(AppError)`
- 禁止依赖：`usecases -> api/routers`、`usecases -> FastAPI Request/Response`（避免业务层被 HTTP 绑死）

### 数据访问（Repo 收敛）

- 复杂查询与 `select(...)` 进入 `infra/repos/*`（或后续 `domain/repos/*`）。
- usecases 只表达意图与流程编排（事务边界、状态流转、调用 repo/infra 组合结果）。

### I/O 与外部依赖收口

- 文件落盘/删除/存在性判断等，优先通过 `infra/storage/*` 统一入口访问。
- 后台任务/向量库/LLM 等外部依赖统一走 `infra/*`，避免散落在多个 usecase 文件里重复实现。

### 小建议（可选但推荐）

- 一个用例函数尽量做到「顶层流程清晰」，把细节拆到 `_validate_*` / `_to_*` / `_*_impl`。
- 同一个资源的字段映射（ORM -> DTO）集中到 `_to_*`，避免在多个函数里复制粘贴字段。
