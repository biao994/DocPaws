"""会话历史拼进 prompt：近几轮原样，更早压缩，超预算再裁。"""


def _truncate_line(line: str, max_len: int) -> str:
    if max_len <= 0 or len(line) <= max_len:
        return line
    if max_len == 1:
        return "…"
    return line[: max_len - 1] + "…"


def format_history_for_prompt(
    lines: list[str],
    *,
    max_chars: int,
    recent_keep: int = 4,
    older_line_max: int = 80,
) -> str:
    """将历史行拼成 prompt 文本。

    - 未超预算：原样拼接
    - 超预算：近 recent_keep 条原样；更早各行截断后放进【更早对话】
    - 仍超：先丢更早摘要行，再丢最近区最旧行（至少留 1 条）
    - max_chars <= 0：不裁
    """
    if not lines:
        return ""
    if max_chars <= 0:
        return "\n".join(lines)

    full = "\n".join(lines)
    if len(full) <= max_chars:
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

    summary = [_truncate_line(line, older_line_max) for line in older]
    text = compose(summary, recent)

    while len(text) > max_chars and summary:
        summary.pop(0)
        text = compose(summary, recent)

    while len(text) > max_chars and len(recent) > 1:
        recent.pop(0)
        text = compose(summary, recent)

    return text
