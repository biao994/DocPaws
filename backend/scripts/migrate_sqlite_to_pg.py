"""
一次性迁移：SQLite (backend/data/docpaws.db) → PostgreSQL

用法（在 backend/ 目录）：
  python scripts/migrate_sqlite_to_pg.py
  python scripts/migrate_sqlite_to_pg.py --pg-url postgresql+psycopg://docpaws:docpaws@127.0.0.1:5432/docpaws
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlmodel import SQLModel, Session

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

DEFAULT_SQLITE = _BACKEND / "data" / "docpaws.db"
DEFAULT_PG = "postgresql+psycopg://docpaws:docpaws@127.0.0.1:5432/docpaws"

# 按外键依赖顺序插入；清空时逆序
TABLE_ORDER = [
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
    "feedback",
    "usagerecord",
]


def _read_sqlite_rows(sqlite_path: Path, table: str) -> list[dict]:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        rows = cur.execute(f"SELECT * FROM [{table}]").fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _pg_column_types(inspector, table: str) -> dict[str, str]:
    return {c["name"]: str(c["type"]).upper() for c in inspector.get_columns(table)}


def _coerce_value(col: str, val, pg_cols: set[str], col_types: dict[str, str]):
    if col not in pg_cols:
        return None
    if val is None:
        return None

    col_type = col_types.get(col, "")
    if "BOOL" in col_type:
        return bool(val)
    if "JSON" in col_type:
        if isinstance(val, str):
            return val
        if isinstance(val, (dict, list)):
            return json.dumps(val, ensure_ascii=False)
        return val

    return val


def _ensure_pg_schema(pg_url: str) -> None:
    import docpaws.domain.models  # noqa: F401
    from docpaws.infra.db.migrate import run_migrations

    engine = create_engine(pg_url, pool_pre_ping=True)
    SQLModel.metadata.create_all(engine)
    # run_migrations uses global engine; temporarily patch via settings
    from docpaws.settings import settings

    settings._database_url = pg_url
    import importlib
    import docpaws.infra.db.session as db_session

    importlib.reload(db_session)
    run_migrations()
    engine.dispose()


def _truncate_pg(session: Session) -> None:
    tables = list(reversed(TABLE_ORDER))
    existing = set(inspect(session.get_bind()).get_table_names())
    for table in tables:
        if table in existing:
            session.exec(text(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE'))
    session.commit()


def migrate(sqlite_path: Path, pg_url: str, dry_run: bool = False) -> None:
    if not sqlite_path.is_file():
        raise SystemExit(f"SQLite 文件不存在: {sqlite_path}")

    print(f"源: {sqlite_path}")
    print(f"目标: {pg_url}")

    counts: dict[str, int] = {}
    for table in TABLE_ORDER:
        counts[table] = len(_read_sqlite_rows(sqlite_path, table))
    print("SQLite 行数:", {k: v for k, v in counts.items() if v})

    if dry_run:
        print("dry-run，未写入 PostgreSQL")
        return

    _ensure_pg_schema(pg_url)
    engine = create_engine(pg_url, pool_pre_ping=True)
    inspector = inspect(engine)

    with Session(engine) as session:
        _truncate_pg(session)

        for table in TABLE_ORDER:
            rows = _read_sqlite_rows(sqlite_path, table)
            if not rows:
                continue
            if table not in inspector.get_table_names():
                print(f"跳过（PG 无表）: {table}")
                continue

            pg_cols = {c["name"] for c in inspector.get_columns(table)}
            col_types = _pg_column_types(inspector, table)
            cols = [c for c in rows[0].keys() if c in pg_cols]
            if not cols:
                continue

            placeholders = ", ".join(f":{c}" for c in cols)
            col_list = ", ".join(f'"{c}"' for c in cols)
            stmt = text(f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})')

            payload = [
                {c: _coerce_value(c, row.get(c), pg_cols, col_types) for c in cols}
                for row in rows
            ]
            session.execute(stmt, payload)
            session.commit()
            print(f"已迁移 {table}: {len(rows)} 行")

    print("迁移完成。请在 backend/.env 设置 DATABASE_URL 并重启 uvicorn。")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate DocPaws SQLite → PostgreSQL")
    parser.add_argument("--sqlite", type=Path, default=DEFAULT_SQLITE)
    parser.add_argument("--pg-url", default=DEFAULT_PG)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrate(args.sqlite, args.pg_url, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
