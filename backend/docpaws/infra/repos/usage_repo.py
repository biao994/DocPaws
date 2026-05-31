"""
用量记录 Repo（运营 / 成本，一期：chat 流式问答）
"""
from __future__ import annotations

import logging

from sqlmodel import Session, select

from docpaws.domain.models.ops import UsageRecord

logger = logging.getLogger(__name__)


def record_chat_stream_usage(
    session: Session,
    *,
    request_id: str,
    kb_id: str | None,
    user_id: str | None,
    chat_mode: str,
    model_name: str,
    latency_ms: int,
    error_code: str | None = None,
) -> UsageRecord | None:
    """写入一次 chat/stream 用量；失败时打日志，不影响主流程。"""
    try:
        row = UsageRecord(
            request_id=request_id,
            kb_id=kb_id,
            user_id=user_id,
            action=f"chat.stream.{chat_mode}",
            latency_ms=max(0, int(latency_ms)),
            tokens_in=0,
            tokens_out=0,
            cost=0.0,
            model_name=model_name or "",
            error_code=error_code,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row
    except Exception as e:
        logger.warning("record_chat_stream_usage failed: %s", e)
        try:
            session.rollback()
        except Exception:
            pass
        return None


def get_usage_by_request_id(session: Session, request_id: str) -> UsageRecord | None:
    stmt = select(UsageRecord).where(UsageRecord.request_id == request_id).limit(1)
    return session.exec(stmt).first()
