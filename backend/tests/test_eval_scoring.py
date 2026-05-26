"""评估打分逻辑单测（不调用 LLM）。"""
from __future__ import annotations

import sys
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[2] / "eval"
if str(EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(EVAL_ROOT))

from lib.scoring import score_answer  # noqa: E402


def test_in_kb_keywords_all_required():
    ok, _ = score_answer(
        "公司成立于2018年",
        must_contain=["2018"],
        expect_reject=False,
        citation_count=1,
    )
    assert ok


def test_in_kb_missing_keyword():
    ok, reason = score_answer(
        "不知道",
        must_contain=["2018"],
        expect_reject=False,
        citation_count=0,
    )
    assert not ok
    assert "missing_keywords" in reason


def test_out_of_kb_reject_phrase():
    ok, _ = score_answer(
        "未检索到相关文档内容，无法回答",
        must_contain=["无法", "未检索"],
        expect_reject=True,
        citation_count=0,
    )
    assert ok


def test_out_of_kb_reject_tone_with_citations():
    ok, reason = score_answer(
        "文档中没有找到马斯克生日相关信息",
        must_contain=[],
        expect_reject=True,
        citation_count=4,
    )
    assert ok
    assert reason == "reject_answer_tone"


def test_out_of_kb_hallucination_fails():
    ok, _ = score_answer(
        "马斯克生日是 6 月 28 日",
        must_contain=["无法"],
        expect_reject=True,
        citation_count=2,
    )
    assert not ok
