# 配置分工（settings vs config）

DocPaws 后端有两处配置入口，职责不同，**不要混用或二次兜底**。

## 一览

| 文件 | 职责 | 典型内容 | 谁读 |
|------|------|----------|------|
| `docpaws/settings.py` | **部署 / 运行时**：环境变量 → `Settings` 单例 | DB、S3、Celery、Redis 缓存、索引目录、`RETRIEVAL_MAX_DISTANCE`、CORS、Session | `app.py`、`infra/*`、部分 usecases |
| `docpaws/config.py` | **模型 / 检索默认项**：`get_default_config()` 字典 | LLM/Embedding 模型名、API Key、chunk 大小、`search_k`、超时与重试 | `chat_service`、`infra/embedding`、`infra/vectorstore`、索引 worker |

## 规则

1. **环境相关** → `settings.py`（读 `backend/.env`），通过 `from docpaws.settings import settings` 使用。
2. **LLM / Embedding / 分块 / 检索条数** → `config.get_default_config()`；需要覆盖时用 `merge_config(user_config)`。
3. **usecases 不要**再写 `getattr(settings, "XXX", "硬编码默认")`；缺项应补进 `settings` 或 `config`，而不是业务层兜底。
4. **测试**可 patch `settings` 实例字段或 mock `get_default_config`，避免在 usecase 里分叉默认值。

## 常见环境变量

### settings（节选）

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | 数据库连接；默认 SQLite `backend/data/docpaws.db` |
| `INDEX_DIR` | FAISS 索引目录（建议英文路径） |
| `S3_*` | MinIO / S3 对象存储 |
| `CELERY_BROKER_URL` | 异步索引任务 |
| `CACHE_REDIS_URL` | 检索结果短 TTL 缓存 |
| `RETRIEVAL_MAX_DISTANCE` | FAISS L2 上限；`<=0` 仅空结果拒答 |
| `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` | 也影响 `config` 中的 LLM Key 解析 |

### config（经 env 注入）

| 变量 | 默认（代码内） |
|------|----------------|
| `LLM_MODEL` | `deepseek-v4-flash` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` |
| `chunk_size` / `chunk_overlap` | 500 / 100（仅 `config.py`，非 env） |
| `search_k` | 5 |

检索阈值标定见 [eval/README.md](../../eval/README.md) 与 `backend/README.md`。

## 相关文档

- [layering.md](./layering.md) — 分层总览
- [backend/README.md](../../backend/README.md) — 启动与目录树
