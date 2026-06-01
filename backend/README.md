# DocPaws Enterprise - 企业级智能文档助手

## 项目结构（分层架构）

```
DocPaws/
  backend/
    docpaws/
      main.py              # 启动入口
      app.py               # App 工厂（中间件/路由注册/事件）
      settings.py          # 统一配置
      config.py            # LLM/Embedding 配置

      api/                 # HTTP 适配层（路由薄）
        deps.py            # Depends 注入
        response.py        # 统一响应/错误码
        schemas/           # Pydantic DTO
        routers/           # 按资源拆分的路由

      domain/              # 领域层
        models/            # SQLModel 表模型（按表族拆分）
        services/          # 纯领域逻辑（如 manifest_diff）

      usecases/            # 业务编排层（风格约定见 docs/architecture/usecases-style.md）

      infra/               # 基础设施层（外部依赖）
        repos/             # Repository（SQL 查询/写入）
        db/session.py      # 数据库引擎 & Session
        storage/local_fs.py # 文件存储
        parsers/pdf_loader.py # PDF 解析
        vectorstore/faiss_manager.py # FAISS 向量库
        llm/chat_client.py # LLM 客户端
        embedding/client.py # Embedding 客户端
        tasks/index_worker.py # 后台索引任务
```

## 分层依赖原则

```
api -> usecases -> domain -> infra（单向依赖）
```

完整说明见 [`docs/architecture/layering.md`](../docs/architecture/layering.md)；usecases 代码约定见 [`usecases-style.md`](../docs/architecture/usecases-style.md)。

- `api/routers/*`：只做校验 → 调用 service → 返回响应
- `usecases/*`：业务流程编排（事务边界、状态流转）
- `infra/repos/*`：所有 DB 查询/写入封装
- `infra/*`：外部系统对接（DB、存储、向量库、任务队列等，可替换）

## 快速启动

```bash
cd DocPaws/backend
pip install -r requirements.txt
cp .env.example .env   # 若无则复制 .env，填入 API Key 等
uvicorn docpaws.main:app --reload --port 8000
```

本地数据统一落在 `backend/data/`（SQLite、`uploads/`、FAISS `indexes/`），路径由 `.env` 的 `DATA_DIR` 等配置，相对路径均相对 `backend/` 解析。

## API 文档

启动后访问 http://localhost:8000/docs

## RAG 评估（Golden 20）

见项目根目录 [`eval/README.md`](../eval/README.md)。首次初始化评估库并跑题：

```bash
cd backend
python ../eval/run_rag_eval.py --setup-only
python ../eval/run_rag_eval.py
```

结果 CSV 输出到 `eval/results/`。

## 检索阈值与拒答

`.env` 可选配置 `RETRIEVAL_MAX_DISTANCE`（FAISS L2，越小越相似；`0` 表示不按距离过滤，仅无结果时拒答）。未过阈值或检索为空时返回：「未检索到足够相关内容，无法基于文档回答。」Agent 流在 `run_agent_stream` 前会做预检（统计/列文档类问题除外）。
