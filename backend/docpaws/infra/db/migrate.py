"""
SQLite 轻量 schema 迁移：补列、从 folder_path 回填 Folder 树
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlmodel import Session, select

from docpaws.domain.models.document import Document
from docpaws.infra.db.session import engine
from docpaws.infra.repos.folder_repo import get_or_create_folder_by_path

logger = logging.getLogger("docpaws.migrate")


def _table_exists(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def _column_exists(inspector, table: str, column: str) -> bool:
    if not _table_exists(inspector, table):
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def run_migrations() -> None:
    inspector = inspect(engine)

    with engine.begin() as conn:
        if _table_exists(inspector, "document") and not _column_exists(inspector, "document", "folder_id"):
            conn.execute(text("ALTER TABLE document ADD COLUMN folder_id VARCHAR"))
            logger.info("Added document.folder_id column")

        if _table_exists(inspector, "document") and not _column_exists(inspector, "document", "thumbnail_key"):
            conn.execute(text("ALTER TABLE document ADD COLUMN thumbnail_key VARCHAR"))
            logger.info("Added document.thumbnail_key column")

        if _table_exists(inspector, "conversation"):
            if not _column_exists(inspector, "conversation", "scope_type"):
                conn.execute(text("ALTER TABLE conversation ADD COLUMN scope_type VARCHAR DEFAULT 'kb'"))
                logger.info("Added conversation.scope_type column")
            if not _column_exists(inspector, "conversation", "scope_id"):
                conn.execute(text("ALTER TABLE conversation ADD COLUMN scope_id VARCHAR"))
                logger.info("Added conversation.scope_id column")

    # 回填：有 folder_path 但无 folder_id 的文档
    with Session(engine) as session:
        docs = list(
            session.exec(
                select(Document).where(
                    Document.folder_path.is_not(None),
                    Document.folder_path != "",
                    Document.folder_id.is_(None),
                )
            ).all()
        )
        changed = 0
        for doc in docs:
            fp = (doc.folder_path or "").strip()
            if not fp:
                continue
            fid = get_or_create_folder_by_path(session, doc.kb_id, fp)
            if fid:
                doc.folder_id = fid
                session.add(doc)
                changed += 1
        if changed:
            session.commit()
            logger.info("Backfilled folder_id for %s documents", changed)
