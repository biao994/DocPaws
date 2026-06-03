# RAG 可复现评估（Golden 20）

固定题库 + 固定 fixture 文档库，一键跑出 CSV，用于对比改检索/Prompt 前后的命中率。

## 目录

| 路径 | 说明 |
|------|------|
| `golden_20.jsonl` | 20 道题（库内 / 库外拒答 / 元数据） |
| `fixtures/*.txt` | 评估用原文（生成 PDF 索引） |
| `run_rag_eval.py` | 主脚本 |
| `lib/scoring.py` | 打分逻辑 |
| `results/eval_*.csv` | 运行输出（默认 gitignore） |
| `.eval_state.json` | 本地 kb_id（gitignore） |

## 前置

在 `backend/` 配置好 `.env`（Embedding + LLM API）。评估会真实调用模型。

可选：启用检索距离阈值（FAISS L2，越小越相似）：

```env
# 0=仅空结果拒答；建议用 golden 标定后设为 0.8~1.5
RETRIEVAL_MAX_DISTANCE=1.2
```

## 命令

```bash
cd backend

# 首次：建库 + 上传 fixture PDF + 同步索引
python ../eval/run_rag_eval.py --setup-only

# 跑 20 题（默认 direct=检索+LLM，读 .eval_state.json 中的 kb_id）
python ../eval/run_rag_eval.py

# 测完整 Agent 链路（含工具调用，流式聚合可能不完整）
python ../eval/run_rag_eval.py --mode agent

# 建库并立刻跑评估
python ../eval/run_rag_eval.py --setup

# 对已启动的 uvicorn（如 8001）发 HTTP
python ../eval/run_rag_eval.py --http --base-url http://127.0.0.1:8001
```

## CSV 字段

`id`, `category`, `question`, `answer`, `citation_count`, `top1_l2`, `latency_ms`, `pass`, `reason`, `model`, `kb_id`, `run_at`

`top1_l2`：direct 模式下、**距离阈值过滤前**最近一条 chunk 的 FAISS L2（越小越相似），用于标定 `RETRIEVAL_MAX_DISTANCE`。

## 题型

- **in_kb**：答案须包含 `must_contain` 关键词
- **out_of_kb**：期望拒答（命中拒答话术或无引用；未做距离阈值前可能仍命中弱相关 chunk）

## 评估模式

| `--mode` | 说明 |
|----------|------|
| `direct`（默认） | 与 `query_knowledge_base` 相同：检索 → Prompt → LLM |
| `agent` | 完整 Agent + `/api/v1/chat` |

## 迭代对比

改代码后重新 `python ../eval/run_rag_eval.py`，对比两次 `results/eval_*.csv` 的 `pass` 列与通过率。
