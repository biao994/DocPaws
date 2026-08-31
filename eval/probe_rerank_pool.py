#!/usr/bin/env python3
"""对比 A-class：FAISS 候选池是否含 gold，以及 rerank 后进不进 final_k。

用法（在 backend/ 下）:
  python ../eval/probe_rerank_pool.py
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parent
GOLDEN = EVAL_ROOT / "golden_20.jsonl"

sys.path.insert(0, str(EVAL_ROOT))
from run_rag_eval import (  # noqa: E402
    EVAL_EMAIL,
    _ensure_backend_path,
    _load_dotenv,
    load_state,
)

# 与 probe / rank_eval 对齐
FOCUS = {
    "q13": "FastAPI",
    "q16": "SQLite",
    "q20": "Cookie",
}


def _first_gold_rank(pairs_or_docs, must: str) -> int | None:
    for i, item in enumerate(pairs_or_docs, start=1):
        doc = item[0] if isinstance(item, tuple) else item
        if must in (doc.page_content or ""):
            return i
    return None


def main() -> int:
    _ensure_backend_path()
    _load_dotenv()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )
    logging.getLogger("docpaws").setLevel(logging.WARNING)

    from sqlmodel import Session, select

    from docpaws.config import get_default_config
    from docpaws.domain.models.user import User
    from docpaws.infra.db.session import engine
    from docpaws.infra.repos.index_repo import get_active_index_artifact
    from docpaws.settings import settings
    from docpaws.usecases.chat_scope import (
        build_faiss_filter,
        document_ids_for_scope,
        retrieval_filter_for_question,
    )
    from docpaws.usecases.chat_service import (
        _apply_rerank_or_degrade,
        _filter_scored_pairs,
        _resolve_retrieval_fetch_k,
        build_retriever,
    )

    state = load_state()
    kb_id = (state or {}).get("kb_id")
    if not kb_id:
        print("No .eval_state.json kb_id. Run: python ../eval/run_rag_eval.py --setup-only", file=sys.stderr)
        return 2

    search_k = int(get_default_config().get("search_k", 5) or 5)
    retrieve_k = search_k
    if settings.RERANK_ENABLED:
        retrieve_k = max(int(settings.RERANK_RETRIEVE_K), search_k)

    print(
        f"RERANK_ENABLED={settings.RERANK_ENABLED} "
        f"PROVIDER={settings.RERANK_PROVIDER} "
        f"MODEL={settings.RERANK_MODEL} "
        f"retrieve_k={retrieve_k} search_k={search_k}"
    )

    items = [
        json.loads(line)
        for line in GOLDEN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    focus_items = [x for x in items if x.get("id") in FOCUS]

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == EVAL_EMAIL)).first()
        if not user:
            print("eval user missing; run --setup-only", file=sys.stderr)
            return 2
        artifact = get_active_index_artifact(session, kb_id)
        if not artifact:
            print("INDEX_NOT_READY", file=sys.stderr)
            return 2

        doc_ids = document_ids_for_scope(session, kb_id=kb_id, scope_type="kb", scope_id=None)
        base_filter = build_faiss_filter(doc_ids)
        _, vectorstore = build_retriever(artifact.index_path)

        for item in focus_items:
            qid = item["id"]
            question = item["question"]
            must = FOCUS[qid]

            meta_filter, _ = retrieval_filter_for_question(
                session,
                kb_id=kb_id,
                scope_type="kb",
                scope_id=None,
                base_filter=base_filter,
                text=question,
            )
            fetch_k = _resolve_retrieval_fetch_k(vectorstore, retrieve_k, meta_filter)
            pairs = vectorstore.similarity_search_with_score(
                question, k=retrieve_k, filter=meta_filter, fetch_k=fetch_k
            )
            pairs = sorted(pairs, key=lambda p: float(p[1]))
            filtered = _filter_scored_pairs(pairs)

            pool_rank = _first_gold_rank(filtered, must)
            docs = _apply_rerank_or_degrade(question, filtered, search_k=search_k) if filtered else []
            final_rank = _first_gold_rank(docs, must)

            print(f"\n=== {qid} · {question}")
            print(f"  must={must!r}")
            print(
                f"  FAISS+L2 候选池: size={len(filtered)} "
                f"gold_rank={pool_rank if pool_rank is not None else 'MISS'}"
            )
            print(
                f"  rerank 后 final_k={search_k}: size={len(docs)} "
                f"gold_rank={final_rank if final_rank is not None else 'MISS'} "
                f"in_prompt={'Y' if final_rank is not None else 'N'}"
            )
            if pool_rank is None:
                print("  → 结论: 候选池就没有 gold（召回/阈值问题，重排救不了）")
            elif final_rank is None:
                print("  → 结论: 池子里有 gold，但重排后没进 top-search_k（排序无效或已降级成 L2）")
            else:
                print(f"  → 结论: gold 已进 prompt（#{final_rank}），若 eval 仍 FAIL 查生成侧")

            # 打印 final 前几段是否含 must，便于肉眼核对
            for i, doc in enumerate(docs, start=1):
                text = (doc.page_content or "").replace("\n", " ")
                mark = "GOLD" if must in (doc.page_content or "") else "-"
                print(f"  final#{i} [{mark}] {text[:100]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
