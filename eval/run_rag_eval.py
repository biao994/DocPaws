#!/usr/bin/env python3
"""
docpaws RAG 可复现评估：golden 集 + 一键出 CSV。

用法（在 backend 目录已配置 .env 的前提下）：

  # 1) 初始化评估知识库（生成 PDF、上传、同步建索引）
  python ../eval/run_rag_eval.py --setup

  # 2) 跑 20 题（默认读 eval/.eval_state.json 里的 kb_id）
  python ../eval/run_rag_eval.py

  # 3) 指定已有知识库
  python ../eval/run_rag_eval.py --kb-id <uuid>

  # 4) 对已运行中的 API 发 HTTP 请求（需先 uvicorn）
  python ../eval/run_rag_eval.py --http --base-url http://127.0.0.1:8001
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# 项目根 = DocPaws
EVAL_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EVAL_ROOT.parent
BACKEND_DIR = REPO_ROOT / "backend"
FIXTURES_DIR = EVAL_ROOT / "fixtures"
GOLDEN_DEFAULT = EVAL_ROOT / "golden_20.jsonl"
STATE_FILE = EVAL_ROOT / ".eval_state.json"
RESULTS_DIR = EVAL_ROOT / "results"

EVAL_EMAIL = "rag_eval@local.dev"
EVAL_PASSWORD = "rag_eval_pass_32chars_min"
EVAL_USERNAME = "rag_eval_user"
KB_NAME = "RAG Eval Golden KB"


def _ensure_backend_path() -> None:
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))


def _load_dotenv() -> None:
    env_path = BACKEND_DIR / ".env"
    if env_path.is_file():
        from dotenv import load_dotenv

        load_dotenv(env_path)


def _cjk_font() -> "fitz.Font":
    """PyMuPDF 内置 CJK 字体，随库走，不依赖系统装雅黑/苹方。"""
    import fitz

    return fitz.Font("china-s")


def _fixture_pdf_content(title: str, body: str) -> str:
    """fixture txt 首行常已是标题，避免 PDF 里重复一行。"""
    text = body.strip()
    if not title.strip():
        return text
    first = text.split("\n", 1)[0].strip()
    if first == title.strip():
        return text
    return f"{title.strip()}\n\n{text}"


def _wrap_text_line(text: str, font: "fitz.Font", fontsize: float, max_width: float) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for ch in text:
        trial = current + ch
        if font.text_length(trial, fontsize=fontsize) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines or [""]


def text_to_pdf(out_path: Path, title: str, body: str) -> None:
    """将 fixture 文本写入 PDF：TextWriter 嵌入 CJK 字体 + 换行 + 分页。"""
    import fitz

    out_path.parent.mkdir(parents=True, exist_ok=True)
    content = _fixture_pdf_content(title, body)
    font = _cjk_font()

    page_w, page_h = 595.0, 842.0
    margin = 50.0
    fontsize = 11.0
    line_height = fontsize * 1.45
    max_width = page_w - 2 * margin
    bottom = page_h - margin

    doc = fitz.open()
    page = doc.new_page(width=page_w, height=page_h)
    writer = fitz.TextWriter(page.rect)
    y = margin

    def _flush_page() -> None:
        nonlocal page, writer, y
        writer.write_text(page)
        page = doc.new_page(width=page_w, height=page_h)
        writer = fitz.TextWriter(page.rect)
        y = margin

    for para in content.split("\n"):
        stripped = para.strip()
        if not stripped:
            y += line_height * 0.6
            if y > bottom:
                _flush_page()
            continue
        for visual_line in _wrap_text_line(stripped, font, fontsize, max_width):
            if y + line_height > bottom:
                _flush_page()
            writer.append((margin, y), visual_line, font=font, fontsize=fontsize)
            y += line_height

    writer.write_text(page)
    doc.save(str(out_path))
    doc.close()


def generate_fixture_pdfs(pdf_dir: Path) -> list[Path]:
    pdf_dir.mkdir(parents=True, exist_ok=True)
    specs = [
        ("company_intro.pdf", "星河科技公司简介", (FIXTURES_DIR / "company_intro.txt").read_text(encoding="utf-8")),
        ("product_manual.pdf", "DocPaws产品手册", (FIXTURES_DIR / "product_manual.txt").read_text(encoding="utf-8")),
    ]
    paths: list[Path] = []
    for filename, title, body in specs:
        p = pdf_dir / filename
        text_to_pdf(p, title, body)
        paths.append(p)
    return paths


def load_golden(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_state() -> dict:
    if STATE_FILE.is_file():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(data: dict) -> None:
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def setup_eval_kb_inprocess() -> str:
    """注册用户、建库、上传 fixture PDF、同步跑索引。返回 kb_id。"""
    _ensure_backend_path()
    _load_dotenv()

    from fastapi.testclient import TestClient

    import docpaws.app as docpaws_app

    app = docpaws_app.create_app()
    client = TestClient(app)

    reg = client.post(
        "/api/v1/auth/register",
        json={"email": EVAL_EMAIL, "username": EVAL_USERNAME, "password": EVAL_PASSWORD},
    )
    if reg.status_code != 200:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": EVAL_EMAIL, "password": EVAL_PASSWORD},
        )
        if login.status_code != 200:
            raise RuntimeError(f"auth failed: register={reg.text} login={login.text}")

    r_kb = client.post(
        "/api/v1/knowledge-bases",
        json={"name": KB_NAME, "description": "RAG eval golden fixtures v1"},
    )
    assert r_kb.status_code == 200, r_kb.text
    kb_id = r_kb.json()["data"]["id"]

    pdf_dir = EVAL_ROOT / "fixtures" / "pdfs"
    pdfs = generate_fixture_pdfs(pdf_dir)
    job_ids: list[str] = []

    for pdf_path in pdfs:
        with pdf_path.open("rb") as f:
            files = {"file": (pdf_path.name, f, "application/pdf")}
            r_up = client.post(
                f"/api/v1/documents?kb_id={kb_id}&on_conflict=auto_rename",
                files=files,
            )
        assert r_up.status_code == 202, r_up.text
        job_ids.append(r_up.json()["data"]["job_id"])

    from docpaws.infra.tasks.index_worker import run_index_job

    for jid in dict.fromkeys(job_ids):
        run_index_job(jid)

    state = {
        "kb_id": kb_id,
        "kb_name": KB_NAME,
        "fixtures_version": "v2",
        "email": EVAL_EMAIL,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state)
    print(f"[setup] kb_id={kb_id} indexed {len(pdfs)} PDFs -> {STATE_FILE}")
    return kb_id


def _http_client(base_url: str):
    import urllib.error
    import urllib.request
    from http.cookiejar import CookieJar

    class Session:
        def __init__(self, base: str):
            self.base = base.rstrip("/")
            self.jar = CookieJar()
            self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

        def post_json(self, path: str, payload: dict, timeout: float = 300) -> dict:
            url = f"{self.base}{path}"
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}, method="POST"
            )
            with self.opener.open(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))

        def post_multipart(self, path: str, field: str, filename: str, content: bytes, timeout: float = 120) -> dict:
            boundary = f"----eval{uuid.uuid4().hex}"
            body = io.BytesIO()
            body.write(f"--{boundary}\r\n".encode())
            body.write(
                f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode()
            )
            body.write(b"Content-Type: application/pdf\r\n\r\n")
            body.write(content)
            body.write(f"\r\n--{boundary}--\r\n".encode())
            url = f"{self.base}{path}"
            req = urllib.request.Request(
                url,
                data=body.getvalue(),
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            )
            with self.opener.open(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))

    return Session(base_url)


def setup_eval_kb_http(base_url: str) -> str:
    s = _http_client(base_url)
    reg = s.post_json(
        "/api/v1/auth/register",
        json={"email": EVAL_EMAIL, "username": EVAL_USERNAME, "password": EVAL_PASSWORD},
    )
    if reg.get("error_code"):
        s.post_json("/api/v1/auth/login", json={"email": EVAL_EMAIL, "password": EVAL_PASSWORD})

    kb = s.post_json("/api/v1/knowledge-bases", json={"name": KB_NAME, "description": "RAG eval golden fixtures v1"})
    kb_id = kb["data"]["id"]

    pdf_dir = EVAL_ROOT / "fixtures" / "pdfs"
    pdfs = generate_fixture_pdfs(pdf_dir)
    job_ids: list[str] = []
    for pdf_path in pdfs:
        content = pdf_path.read_bytes()
        up = s.post_multipart(
            f"/api/v1/documents?kb_id={kb_id}&on_conflict=auto_rename",
            "file",
            pdf_path.name,
            content,
        )
        job_ids.append(up["data"]["job_id"])

    _ensure_backend_path()
    _load_dotenv()
    from docpaws.infra.tasks.index_worker import run_index_job

    for jid in dict.fromkeys(job_ids):
        run_index_job(jid)

    save_state({"kb_id": kb_id, "kb_name": KB_NAME, "fixtures_version": "v2", "email": EVAL_EMAIL})
    return kb_id


def _eval_retrieve_docs_and_top1_l2(
    vectorstore,
    question: str,
    *,
    search_k: int,
    metadata_filter,
) -> tuple[list, float | None]:
    """与线上一致的检索；返回 (过滤后 docs, 过滤前 top1 L2，越小越相似)。"""
    from docpaws.usecases.chat_service import (
        _filter_scored_pairs,
        _resolve_retrieval_fetch_k,
        docs_from_scored_pairs,
    )

    fetch_k = _resolve_retrieval_fetch_k(vectorstore, search_k, metadata_filter)
    if hasattr(vectorstore, "similarity_search_with_score"):
        pairs = vectorstore.similarity_search_with_score(
            question,
            k=search_k,
            filter=metadata_filter,
            fetch_k=fetch_k,
        )
    else:
        raw = vectorstore.similarity_search(
            question,
            k=search_k,
            filter=metadata_filter,
            fetch_k=fetch_k,
        )
        pairs = [(d, 0.0) for d in raw]
    top1 = min((float(s) for _, s in pairs), default=None) if pairs else None
    filtered = _filter_scored_pairs(pairs)
    docs = docs_from_scored_pairs(filtered, limit=search_k)
    return docs, top1


def chat_direct(
    kb_id: str, question: str, chat_mode: str = "fast"
) -> tuple[str, int, int, str | None, float | None]:
    """直连检索 + LLM（与 query_knowledge_base 一致），评估更稳定。"""
    _ensure_backend_path()
    _load_dotenv()

    from sqlmodel import Session, select

    from docpaws.config import get_default_config
    from docpaws.domain.models.user import User
    from docpaws.infra.db.session import engine
    from docpaws.infra.repos.index_repo import get_active_index_artifact
    from docpaws.usecases.chat_llm import create_chat_llm, resolve_chat_model
    from docpaws.usecases.chat_scope import (
        build_faiss_filter,
        document_ids_for_scope,
        document_title_for_id,
        retrieval_filter_for_question,
        scope_cache_token,
    )
    from docpaws.usecases.chat_service import (
        INSUFFICIENT_RETRIEVAL_MSG,
        build_prompt,
        build_retriever,
        get_citations_from_docs,
    )

    cfg = get_default_config()
    model_name = resolve_chat_model(cfg.get("model"))
    search_k = int(cfg.get("search_k", 5) or 5)
    t0 = time.perf_counter()

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == EVAL_EMAIL)).first()
        if not user:
            return "", 0, int((time.perf_counter() - t0) * 1000), "eval user not found; run --setup-only", None

        artifact = get_active_index_artifact(session, kb_id)
        if not artifact:
            return "", 0, int((time.perf_counter() - t0) * 1000), "INDEX_NOT_READY", None

        scope_type, scope_id = "kb", None
        doc_ids = document_ids_for_scope(session, kb_id=kb_id, scope_type=scope_type, scope_id=scope_id)
        metadata_filter = build_faiss_filter(doc_ids)

        try:
            _, vectorstore = build_retriever(artifact.index_path)
        except FileNotFoundError:
            return "", 0, int((time.perf_counter() - t0) * 1000), "INDEX_FILE_NOT_FOUND", None

        meta_filter, named_doc_id = retrieval_filter_for_question(
            session,
            kb_id=kb_id,
            scope_type=scope_type,
            scope_id=scope_id,
            base_filter=metadata_filter,
            text=question,
        )
        docs, top1_l2 = _eval_retrieve_docs_and_top1_l2(
            vectorstore,
            question,
            search_k=search_k,
            metadata_filter=meta_filter,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)

        if not docs:
            return INSUFFICIENT_RETRIEVAL_MSG, 0, latency_ms, None, top1_l2

        context_str = "\n\n".join(d.page_content for d in docs)
        target_title = document_title_for_id(session, named_doc_id) if named_doc_id else None
        prompt = build_prompt("", context_str, question, target_document=target_title)
        llm = create_chat_llm(model_name=model_name, chat_mode=chat_mode)
        try:
            resp = llm.invoke(prompt)
            text = (getattr(resp, "content", None) or str(resp)).strip() or "未能生成回答。"
        except Exception as e:
            return "", 0, latency_ms, str(e), top1_l2

        citations = get_citations_from_docs(docs, session)
        return text, len(citations), latency_ms, None, top1_l2


def chat_inprocess(client, kb_id: str, question: str, chat_mode: str = "fast") -> tuple[str, int, int, str | None]:
    t0 = time.perf_counter()
    r = client.post(
        "/api/v1/chat",
        json={"kb_id": kb_id, "question": question, "conversation_id": None, "chat_mode": chat_mode},
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    if r.status_code != 200:
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        err = body.get("error_code") or body.get("message") or r.text
        return "", 0, latency_ms, str(err)

    data = r.json().get("data") or {}
    answer = data.get("answer") or ""
    citations = data.get("citations") or []
    return answer, len(citations), latency_ms, None


def chat_http(session, kb_id: str, question: str, chat_mode: str = "fast") -> tuple[str, int, int, str | None]:
    t0 = time.perf_counter()
    try:
        body = session.post_json(
            "/api/v1/chat",
            {"kb_id": kb_id, "question": question, "conversation_id": None, "chat_mode": chat_mode},
        )
    except Exception as e:
        return "", 0, int((time.perf_counter() - t0) * 1000), str(e)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    if body.get("error_code"):
        return "", 0, latency_ms, body.get("message") or body.get("error_code")
    data = body.get("data") or {}
    return data.get("answer") or "", len(data.get("citations") or []), latency_ms, None


def run_eval(
    kb_id: str,
    golden_path: Path,
    output_path: Path,
    *,
    use_http: bool = False,
    base_url: str = "http://127.0.0.1:8001",
    chat_mode: str = "fast",
    eval_mode: str = "direct",
) -> dict:
    if str(EVAL_ROOT) not in sys.path:
        sys.path.insert(0, str(EVAL_ROOT))
    from lib.scoring import score_answer

    golden = load_golden(golden_path)
    _load_dotenv()
    model_name = os.getenv("LLM_MODEL", "unknown")

    client = None
    http_sess = None
    if eval_mode == "agent":
        if use_http:
            http_sess = _http_client(base_url)
            login = http_sess.post_json(
                "/api/v1/auth/login", {"email": EVAL_EMAIL, "password": EVAL_PASSWORD}
            )
            if login.get("error_code"):
                http_sess.post_json(
                    "/api/v1/auth/register",
                    {
                        "email": EVAL_EMAIL,
                        "username": EVAL_USERNAME,
                        "password": EVAL_PASSWORD,
                    },
                )
        else:
            _ensure_backend_path()
            from fastapi.testclient import TestClient
            import docpaws.app as docpaws_app

            client = TestClient(docpaws_app.create_app())
            login = client.post(
                "/api/v1/auth/login",
                json={"email": EVAL_EMAIL, "password": EVAL_PASSWORD},
            )
            if login.status_code != 200:
                client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": EVAL_EMAIL,
                        "username": EVAL_USERNAME,
                        "password": EVAL_PASSWORD,
                    },
                )

    rows_out: list[dict] = []
    passed = 0

    for item in golden:
        qid = item["id"]
        question = item["question"]
        top1_l2: float | None = None
        if eval_mode == "direct" and not use_http:
            answer, cit_n, latency_ms, err, top1_l2 = chat_direct(kb_id, question, chat_mode)
        elif eval_mode == "agent" and use_http:
            answer, cit_n, latency_ms, err = chat_http(http_sess, kb_id, question, chat_mode)
        elif eval_mode == "agent":
            answer, cit_n, latency_ms, err = chat_inprocess(client, kb_id, question, chat_mode)
        else:
            answer, cit_n, latency_ms, err = chat_http(http_sess, kb_id, question, chat_mode)

        ok, reason = score_answer(
            answer,
            must_contain=item.get("must_contain"),
            expect_reject=bool(item.get("expect_reject")),
            citation_count=cit_n,
        )
        if err:
            ok = False
            reason = f"api_error:{err}"

        if ok:
            passed += 1

        rows_out.append(
            {
                "run_at": datetime.now(timezone.utc).isoformat(),
                "kb_id": kb_id,
                "model": model_name,
                "eval_mode": eval_mode,
                "chat_mode": chat_mode,
                "id": qid,
                "category": item.get("category", ""),
                "question": question,
                "answer": answer[:2000],
                "citation_count": cit_n,
                "top1_l2": "" if top1_l2 is None else round(top1_l2, 4),
                "latency_ms": latency_ms,
                "pass": ok,
                "reason": reason,
                "error": err or "",
            }
        )
        status = "PASS" if ok else "FAIL"
        l2_hint = f" top1_l2={top1_l2:.4f}" if top1_l2 is not None else ""
        print(f"  [{status}] {qid} ({latency_ms}ms){l2_hint} {reason}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows_out[0].keys()) if rows_out else []
    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)

    summary = {
        "total": len(golden),
        "passed": passed,
        "pass_rate": round(passed / len(golden), 4) if golden else 0,
        "output": str(output_path),
    }
    print(f"\n[done] {passed}/{len(golden)} passed -> {output_path}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="docpaws RAG golden eval -> CSV")
    parser.add_argument("--setup", action="store_true", help="创建评估 KB 并索引 fixture PDF")
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="仅执行 --setup，不跑 golden（可与 --setup 联用）",
    )
    parser.add_argument("--golden", type=Path, default=GOLDEN_DEFAULT)
    parser.add_argument("--kb-id", type=str, default="", help="知识库 ID（默认读 .eval_state.json）")
    parser.add_argument("--output", type=Path, default=None, help="CSV 输出路径")
    parser.add_argument("--http", action="store_true", help="请求已运行的 uvicorn 而非进程内 TestClient")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--chat-mode", choices=["fast", "deep"], default="fast")
    parser.add_argument(
        "--mode",
        choices=["direct", "agent"],
        default="direct",
        help="direct=检索+LLM（默认，稳定）；agent=完整 Agent 链路",
    )
    args = parser.parse_args()

    if args.setup or args.setup_only:
        if args.http:
            setup_eval_kb_http(args.base_url)
        else:
            setup_eval_kb_inprocess()
        if args.setup_only:
            return 0

    kb_id = args.kb_id or load_state().get("kb_id")
    if not kb_id:
        print("缺少 kb_id：先运行 python eval/run_rag_eval.py --setup", file=sys.stderr)
        return 1

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.output or (RESULTS_DIR / f"eval_{ts}.csv")

    run_eval(
        kb_id,
        args.golden,
        out,
        use_http=args.http,
        base_url=args.base_url,
        chat_mode=args.chat_mode,
        eval_mode=args.mode,
    )
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(EVAL_ROOT))
    raise SystemExit(main())
