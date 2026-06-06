"""校验 SQLite → PG 迁移行数是否一致。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, text

SQLITE = Path(__file__).resolve().parents[1] / "data" / "docpaws.db"
PG = "postgresql+psycopg://docpaws:docpaws@127.0.0.1:5432/docpaws"

TABLES = [
    "user",
    "knowledgebase",
    "kb_folder",
    "fileobject",
    "kbfile",
    "indexjob",
    "indexartifact",
    "indexartifactmanifest",
    "document",
    "chunk",
    "conversation",
    "message",
    "answer",
    "retrievalrun",
    "usagerecord",
]


def sqlite_count(table: str) -> int:
    conn = sqlite3.connect(SQLITE)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def pg_count(engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()


def main() -> None:
    engine = create_engine(PG)
    ok = True
    for table in TABLES:
        s = sqlite_count(table)
        p = pg_count(engine, table)
        mark = "OK" if s == p else "MISMATCH"
        if s != p:
            ok = False
        if s or p:
            print(f"{table:24} sqlite={s:5} pg={p:5} {mark}")
    if not ok:
        raise SystemExit(1)
    print("all counts match")


if __name__ == "__main__":
    main()
