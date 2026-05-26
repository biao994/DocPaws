"""RAG 评估打分逻辑（与 run_rag_eval 共用，便于单测）。"""
from __future__ import annotations

_REJECT_PHRASES = (
    "无法",
    "未检索",
    "没有相关",
    "无法回答",
    "无法基于",
    "未检索到足够相关内容",
    "信息不足",
    "没有找到",
    "未涉及",
    "并未包含",
    "没有提及",
)


def score_answer(
    answer: str,
    *,
    must_contain: list[str] | None,
    expect_reject: bool,
    citation_count: int,
) -> tuple[bool, str]:
    """
    返回 (pass, reason)。
    expect_reject=True：命中 must_contain 任一，或答案含常见拒答话术即通过。
    """
    text = (answer or "").strip()
    lower = text.lower()
    keywords = [k for k in (must_contain or []) if k]

    if expect_reject:
        if keywords and any(k.lower() in lower for k in keywords):
            return True, "reject_phrase_hit"
        if any(p in text for p in _REJECT_PHRASES):
            return True, "reject_answer_tone"
        return False, "expected_reject_but_answered"

    if not keywords:
        return bool(text), "nonempty_answer"

    missing = [k for k in keywords if k.lower() not in lower]
    if missing:
        return False, f"missing_keywords:{','.join(missing)}"
    return True, "keywords_ok"
