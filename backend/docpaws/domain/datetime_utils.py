from datetime import UTC, datetime


def utc_now() -> datetime:
    # SQLite 存 naive UTC；与历史 utcnow() 行为一致，避免 aware/naive 混比
    return datetime.now(UTC).replace(tzinfo=None)
