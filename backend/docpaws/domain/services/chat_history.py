"""会话历史拼进 prompt：近几轮原样，更早压缩，超 token 预算再裁。

用固定编码（cl100k_base）粗估 token，挡上下文撑爆即可，不追求与线上模型逐 token 一致。
"""
from __future__ import annotations

from functools import lru_cache

import tiktoken

# OpenAI 兼容栈常用编码；固定一种即可粗估，不必按模型精确对齐
_HISTORY_ENCODING_NAME = "cl100k_base"


@lru_cache(maxsize=1)
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(_HISTORY_ENCODING_NAME)


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_encoding().encode(text))


def _truncate_to_tokens(line: str, max_tokens: int) -> str:
    """按 token 截断一行；decode 切在 token 边界上。"""
    if max_tokens <= 0:
        return line
    enc = _encoding()
    ids = enc.encode(line)
    if len(ids) <= max_tokens:
        return line
    return enc.decode(ids[:max_tokens])


def format_history_for_prompt(
    lines: list[str],
    *,
    max_tokens: int,
    recent_keep: int = 4,
    older_line_max: int = 40,
) -> str:
    """将历史行拼成 prompt 文本。

    - 未超预算：原样拼接
    - 超预算：近 recent_keep 条原样；更早各行按 token 截断后放进【更早对话】
    - 仍超：先丢更早摘要行，再丢最近区最旧行（至少留 1 条）
    - max_tokens <= 0：不裁
    """
    if not lines:
        return ""
    if max_tokens <= 0:
        return "\n".join(lines)

    full = "\n".join(lines)
    if count_tokens(full) <= max_tokens:
        return full

    keep = max(1, min(recent_keep, len(lines)))
    older = lines[:-keep]
    recent = list(lines[-keep:])

    def compose(summary_lines: list[str], recent_lines: list[str]) -> str:
        recent_text = "\n".join(recent_lines)
        if not summary_lines:
            return recent_text
        return (
            "【更早对话】\n"
            + "\n".join(summary_lines)
            + "\n【最近对话】\n"
            + recent_text
        )

    summary = [_truncate_to_tokens(line, older_line_max) for line in older]
    text = compose(summary, recent)

    while count_tokens(text) > max_tokens and summary:
        summary.pop(0)
        text = compose(summary, recent)

    while count_tokens(text) > max_tokens and len(recent) > 1:
        recent.pop(0)
        text = compose(summary, recent)

    return text
