# DocPaws

企业级 RAG 文档助手：知识库管理、PDF 索引、流式对话、引用与检索阈值拒答。  
后端 FastAPI + SQLModel，前端 Vue 3 + Vite。

## 仓库结构

```
DocPaws/
  backend/          # FastAPI API、索引 worker、Celery 任务
  frontend/         # Vue 3 单页应用
  eval/             # Golden 20 RAG 回归评估
  docs/             # 架构与开发约定
  docker-compose.yml  # 本地 Redis + MinIO
```

架构文档见 [`docs/architecture/layering.md`](docs/architecture/layering.md)（分层总览）、[`usecases-style.md`](docs/architecture/usecases-style.md)（用例层约定）。  
详细后端说明见 [`backend/README.md`](backend/README.md)。  
评估说明见 [`eval/README.md`](eval/README.md)。

## 环境要求

- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) 或 Anaconda（推荐用 **Conda** 管理后端 Python，避免和系统 Python 混用）
- Python **3.11**（由 Conda 环境提供即可）
- Node.js 20+（前端，与 Conda 无关）
- [Docker](https://docs.docker.com/get-docker/)（可选：`docker compose up -d` 起 Redis + MinIO）
- Redis（可选：检索缓存、Celery 索引队列；可用 compose 或本机已有实例）
- LLM + Embedding 的 API Key（DeepSeek / OpenAI 兼容 / SiliconFlow 等）

## 快速启动

### 0. 基础设施（Redis + MinIO，推荐）

在项目根目录 `DocPaws/`：

```bash
docker compose up -d
```

| 服务 | 地址 | 说明 |
|------|------|------|
| **MinIO** API | `http://127.0.0.1:9000` | 上传 PDF 对象存储 |
| **MinIO** 控制台 | `http://127.0.0.1:9001` | 账号 `minioadmin` / `minioadmin123` |
| **Redis** | `127.0.0.1:6379` | DB `/0` 检索缓存，`/1` Celery broker，`/2` result |

`minio-init` 会自动创建 bucket `kb-files` 后退出（`Exited (0)` 属正常）。

若本机 **6379 已被占用**，只起 MinIO 即可：

```bash
docker compose up -d minio minio-init
```

`.env` 中 Redis / MinIO 变量见 [`.env.example`](backend/.env.example)（复制为 `backend/.env` 后按需改 Key）。

停止：`docker compose down`（数据在 Docker volume 中保留）。

### 1. 后端（Conda + pip）

在**项目根目录** `DocPaws/` 下操作。以下命令在 **Anaconda Prompt** 或已执行过 `conda init` 的终端中使用。

**① 创建并激活环境（只需做一次）**

```bash
conda create -n docpaws python=3.11 -y
conda activate docpaws
```

**② 安装依赖并配置**

```bash
cd backend
pip install -r requirements.txt
```

Windows PowerShell 若没有 `cp`，可复制模板：

```powershell
Copy-Item .env.example .env
```

macOS / Linux：

```bash
cp .env.example .env
```

用编辑器打开 `backend/.env`，填入 `DEEPSEEK_API_KEY`、`EMBEDDING_API_KEY` 等（参见 `.env.example` 注释）。

**③ 启动 API**

```bash
# 确保仍在 backend/ 且已 conda activate docpaws
uvicorn docpaws.main:app --reload --port 8000
```

- API 文档：<http://localhost:8000/docs>
- 本地数据默认在 `backend/data/`（SQLite、`uploads/`、FAISS 索引）

> **说明**：Conda 只负责隔离 Python 版本；`requirements.txt` 里的包（含 `faiss-cpu`）仍用 **pip** 安装，这是 Python 数据项目的常见做法。  
> 以后每次开发前先执行：`conda activate docpaws`。

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

- 开发地址：默认 <http://localhost:3000>（`vite.config.js` 可改端口；若用 3001 等亦可）
- 前端 `/api` 由 Vite **代理到** `http://127.0.0.1:8000`，须与下面 uvicorn 端口一致；改后端端口时请同步改 `frontend/vite.config.js` 的 `proxy.target`
- `backend/.env` 中 `CORS_ORIGINS` 需包含你的前端 Origin（如 `http://localhost:3000`）

### 3. 可选：索引 Worker

上传 PDF 后需建向量索引。若配置了 `CELERY_BROKER_URL`，**再开一个终端**，同样先 `conda activate docpaws`，然后在 `backend/` 执行：

先 `cd backend`，再按系统选择（均需已 `conda activate docpaws`）：

```bash
# Linux / macOS
celery -A docpaws.infra.tasks.celery_app:celery_app worker --loglevel=info

# Windows（默认 prefork 池不兼容，需 solo）
celery -A docpaws.infra.tasks.celery_app:celery_app worker --loglevel=info --pool=solo
```

未配置 Celery 时，部分环境会同步或内联执行索引（以当前代码为准）。

## 常用命令

| 目录 | 命令 | 说明 |
|------|------|------|
| `backend/` | `pytest tests/ -q` | 后端测试（79+ 用例） |
| `frontend/` | `npm run typecheck` | Vue/TS 类型检查 |
| `frontend/` | `npm run build` | 生产构建 |
| `backend/`（已 `conda activate docpaws`） | `python ../eval/run_rag_eval.py` | Golden 20 评估 |

## 核心能力

- 个人知识库、文件夹、PDF 上传与 **manifest 增量索引**
- RAG 对话（**scope**：全库 / 文件夹 / 单文件）、流式 SSE、思考过程展示
- **检索距离阈值拒答**（`RETRIEVAL_MAX_DISTANCE`）
- Golden 20 可复现评估（`eval/`）

## 配置说明

复制 [`backend/.env.example`](backend/.env.example) 为 `backend/.env`，**勿将 `.env` 提交到 Git**。

关键变量：

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` / `EMBEDDING_API_KEY` | LLM 与向量模型 |
| `INDEX_DIR` | FAISS 索引目录（Windows 建议纯英文路径） |
| `RETRIEVAL_MAX_DISTANCE` | L2 距离上限，`0` 表示仅无检索结果时拒答 |
| `CELERY_BROKER_URL` / `CACHE_REDIS_URL` | 异步索引与检索缓存（可选） |
| `S3_ENDPOINT_INTERNAL` | MinIO 对象存储（上传 PDF 需要） |

## 许可证

本项目采用 [MIT License](LICENSE)。

生产部署前请更换 `SECRET_KEY`，并审查 FAISS 索引目录权限。

