#!/usr/bin/env python3
"""Dump FAISS top-k ranks for Golden in_kb questions (no LLM).

Marks gold rank = first chunk containing any must_contain keyword.
A-class smell: gold in top-20 but rank > search_k (default 5), or gold in 3–5.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EVAL_ROOT.parent
BACKEND_DIR = REPO_ROOT / "backend"
GOLDEN = EVAL_ROOT / "golden_20.jsonl"
STATE_FILE = EVAL_ROOT / ".eval_state.json"
OUT = EVAL_ROOT / "results" / "topk_rank_probe.md"

sys.path.insert(0, str(EVAL_ROOT))
from run_rag_eval import (  # noqa: E402
    EVAL_EMAIL,
    _ensure_backend_path,
    _load_dotenv,
    load_state,
)


def main() -> int:
    _ensure_backend_path()
    _load_dotenv()

    from sqlmodel import Session, select

    from docpaws.config import get_default_config
    from docpaws.domain.models.user import User
    from docpaws.infra.db.session import engine
    from docpaws.infra.repos.index_repo import get_active_index_artifact
    from docpaws.usecases.chat_scope import (
        build_faiss_filter,
        document_ids_for_scope,
        retrieval_filter_for_question,
    )
    from docpaws.usecases.chat_service import (
        _filter_scored_pairs,
        _resolve_retrieval_fetch_k,
        build_retriever,
    )

    state = load_state()
    kb_id = (state or {}).get("kb_id")
    if not kb_id:
        print("No .eval_state.json kb_id. Run: python ../eval/run_rag_eval.py --setup-only", file=sys.stderr)
        return 2

    items = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]
    in_kb = [x for x in items if not x.get("expect_reject")]
    search_k = int(get_default_config().get("search_k", 5) or 5)
    probe_k = 10

    summary_rows: list[str] = []
    details: list[str] = []
    a_class: list[str] = []

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

        for item in in_kb:
            qid = item["id"]
            question = item["question"]
            musts = item.get("must_contain") or []
            meta_filter, _ = retrieval_filter_for_question(
                session,
                kb_id=kb_id,
                scope_type="kb",
                scope_id=None,
                base_filter=base_filter,
                text=question,
            )
            fetch_k = _resolve_retrieval_fetch_k(vectorstore, probe_k, meta_filter)
            pairs = vectorstore.similarity_search_with_score(
                question, k=probe_k, filter=meta_filter, fetch_k=fetch_k
            )
            pairs = sorted(pairs, key=lambda p: float(p[1]))
            filtered = _filter_scored_pairs(pairs)
            filtered_ids = {id(d) for d, _ in filtered}

            gold_rank = None
            for i, (doc, _score) in enumerate(pairs, start=1):
                text = doc.page_content or ""
                if any(m in text for m in musts):
                    gold_rank = i
                    break

            in_prompt = gold_rank is not None and gold_rank <= search_k
            must_s = "/".join(musts)
            summary_rows.append(
                f"| {qid} | {gold_rank if gold_rank is not None else 'MISS'} | "
                f"{'Y' if in_prompt else 'N'} | {must_s} | {question} |"
            )

            details.append(f"## {qid} · {question}")
            details.append("")
            details.append(f"- must_contain: `{musts}`")
            details.append(f"- gold_rank: **{gold_rank}**")
            details.append(f"- 进 top-{search_k}（当前 prompt）: **{'是' if in_prompt else '否'}**")
            details.append("")
            details.append("### 检索返回（按 L2 升序，越小越近）")
            details.append("")
            for i, (doc, score) in enumerate(pairs, start=1):
                text = doc.page_content or ""
                is_gold = any(m in text for m in musts)
                kept = id(doc) in filtered_ids
                tag = []
                if is_gold:
                    tag.append("GOLD")
                tag.append("会进阈值后候选" if kept else "被距离阈值滤掉")
                if i <= search_k:
                    tag.append(f"当前会进 prompt(top{search_k})")
                details.append(f"#### #{i} · L2={float(score):.4f} · {' · '.join(tag)}")
                details.append("")
                details.append("```text")
                details.append(text.strip() or "(empty)")
                details.append("```")
                details.append("")

            if gold_rank is not None and gold_rank >= 3:
                a_class.append(f"{qid}: gold_rank={gold_rank} (in_prompt={'Y' if in_prompt else 'N'})")

    lines = [
        "# Golden top-k rank probe",
        "",
        "怎么读：上面是总表；下面每道题有完整检索片段（不是摘要）。`GOLD` = 含答案关键词的那段。",
        "",
        f"- kb_id: `{kb_id}`",
        f"- search_k (prompt): {search_k}",
        f"- probe_k: {probe_k}",
        "",
        "**A-class candidates (gold_rank≥3):** "
        + (", ".join(a_class) if a_class else "none on this fixture set"),
        "",
        "## 总表",
        "",
        "| id | gold_rank | in_prompt? | must | question |",
        "|----|-----------|------------|------|----------|",
        *summary_rows,
        "",
        "## 逐题检索片段",
        "",
        *details,
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    print("A-class candidates:", a_class or ["none"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
