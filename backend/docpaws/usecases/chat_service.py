"""
对话问答业务编排（Agent + 工具）

流程：
1. 验证 KB / 索引 / 会话范围
2. 保存用户消息并返回 meta
3. create_agent 按问题选用工具（检索 / 统计 / 列表 / 关键词搜索）
4. 流式输出最终回答并保存引用
"""
import json
import hashlib
import logging
import re
import time
import traceback
from typing import AsyncGenerator

import redis
from sqlmodel import Session

from docpaws.api.response import ErrorCode, get_status_code, ERROR_CODE_TO_HINT
from docpaws.api.authz import require_kb_owned
from docpaws.errors import AppError
from docpaws.config import get_default_config
from docpaws.infra.vectorstore.faiss_manager import VectorStoreManager
from docpaws.usecases.chat_llm import ChatMode, create_chat_llm, resolve_chat_model
from docpaws.usecases.chat_thinking import stream_thinking_prelude
from docpaws.usecases.chat_scope import count_documents_in_scope, scope_prompt_label
from docpaws.domain.models.document import Chunk, Document
from docpaws.domain.models.chat import Conversation, Message
from docpaws.domain.models.index import Answer, RetrievalRun
from docpaws.infra.repos.index_repo import get_active_index_artifact
from docpaws.settings import settings
from docpaws.infra.repos.conversation_repo import (
    get_conversation_by_id,
    create_conversation,
    get_recent_history_text,
)

logger = logging.getLogger(__name__)

# 检索未过阈值 / 无命中时的统一拒答（工具与 Agent 预检共用）
INSUFFICIENT_RETRIEVAL_MSG = "未检索到足够相关内容，无法基于文档回答。"

_WS_RE = re.compile(r"\s+")
_META_PREFLIGHT_SKIP_RE = re.compile(
    r"(几个|多少|有哪些|列出|列表).{0,12}(文件|文档)|"
    r"(文件|文档).{0,8}(几个|多少|有哪些|列出|列表)"
)


def _normalize_question(q: str) -> str:
    return _WS_RE.sub(" ", (q or "").strip())


def _retrieval_cache_key(
    *,
    kb_id: str,
    artifact_id: str,
    search_k: int,
    question_norm: str,
    scope_token: str,
) -> str:
    digest = hashlib.sha256(question_norm.encode("utf-8")).hexdigest()[:24]
    prefix = (getattr(settings, "CACHE_REDIS_PREFIX", "docpaws:retrieve:") or "docpaws:retrieve:").strip()
    return f"{prefix}{kb_id}:{artifact_id}:{search_k}:{scope_token}:{digest}"


def _serialize_docs_for_cache(docs: list) -> str:
    return json.dumps(
        [{"page_content": d.page_content, "metadata": (d.metadata or {})} for d in docs],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _deserialize_docs_from_cache(raw: bytes):
    from langchain_core.documents import Document as LCDocument

    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, list):
        return None
    docs: list[LCDocument] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        page_content = item.get("page_content")
        metadata = item.get("metadata") or {}
        if not isinstance(page_content, str) or not isinstance(metadata, dict):
            continue
        docs.append(LCDocument(page_content=page_content, metadata=metadata))
    return docs


def build_retriever(index_path: str):
    """构建 FAISS 检索器"""
    cfg = get_default_config()
    vsm = VectorStoreManager(cfg)
    vsm.load_vector_store(index_path)
    return vsm.get_retriever(), vsm.vectorstore


def retrieval_max_distance() -> float | None:
    """RETRIEVAL_MAX_DISTANCE>0 时启用 L2 距离过滤（越小越相似）。"""
    v = float(getattr(settings, "RETRIEVAL_MAX_DISTANCE", 0) or 0)
    return v if v > 0 else None


def _filter_scored_pairs(pairs: list[tuple]) -> list[tuple]:
    max_d = retrieval_max_distance()
    if max_d is None:
        return pairs
    return [(doc, score) for doc, score in pairs if float(score) <= max_d]


def docs_from_scored_pairs(pairs: list[tuple], *, limit: int) -> list:
    out: list = []
    for doc, score in pairs[:limit]:
        meta = dict(doc.metadata or {})
        meta["_retrieval_score"] = float(score)
        doc.metadata = meta
        out.append(doc)
    return out


def hit_chunks_from_docs(docs: list) -> list[dict]:
    return [
        {
            "chunk_id": (d.metadata or {}).get("chunk_id"),
            "score": float((d.metadata or {}).get("_retrieval_score", 0)),
        }
        for d in docs
    ]


def should_skip_retrieval_preflight(question: str) -> bool:
    """统计/列文档类问题不走检索预检，避免挡住 count/list 工具。"""
    q = _normalize_question(question)
    return bool(_META_PREFLIGHT_SKIP_RE.search(q))


def retrieve_docs_with_retry(
    vectorstore,
    question: str,
    *,
    search_k: int,
    metadata_filter=None,
    max_retries: int = 2,
) -> list:
    """向量检索（带分数 + 可选距离阈值）；metadata_filter 为 None 时检索整库。"""
    fetch_k = max(search_k * 4, 20)
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            if hasattr(vectorstore, "similarity_search_with_score"):
                pairs = vectorstore.similarity_search_with_score(
                    question,
                    k=fetch_k,
                    filter=metadata_filter,
                    fetch_k=fetch_k,
                )
            else:
                raw = vectorstore.similarity_search(
                    question,
                    k=fetch_k,
                    filter=metadata_filter,
                    fetch_k=fetch_k,
                )
                pairs = [(d, 0.0) for d in raw]
            filtered = _filter_scored_pairs(pairs)
            return docs_from_scored_pairs(filtered, limit=search_k)
        except Exception as e:
            last_error = e
            logger.warning(
                "similarity_search_with_score failed (attempt %s/%s): %s",
                attempt + 1,
                max_retries + 1,
                e,
            )
            if attempt < max_retries:
                time.sleep(0.5 * (attempt + 1))
    raise last_error


def retrieve_scoped_docs_cached(
    *,
    kb_id: str,
    question: str,
    search_k: int,
    metadata_filter,
    vectorstore,
    cache_redis: redis.Redis | None,
    artifact_id: str,
    scope_token: str,
) -> list:
    """带 Redis 缓存的范围内向量检索（供 query_knowledge_base 工具调用）。"""
    question_norm = _normalize_question(question)
    cache_key = ""
    docs = None

    if cache_redis is not None:
        try:
            cache_key = _retrieval_cache_key(
                kb_id=kb_id,
                artifact_id=artifact_id,
                search_k=search_k,
                question_norm=question_norm,
                scope_token=scope_token,
            )
            cached = cache_redis.get(cache_key)
            if cached:
                docs = _deserialize_docs_from_cache(cached)
        except Exception as e:
            logger.info(f"retrieval cache get failed: {e}")
            docs = None

    if docs is None:
        docs = retrieve_docs_with_retry(
            vectorstore,
            question_norm,
            search_k=search_k,
            metadata_filter=metadata_filter,
        )
        if cache_redis is not None and cache_key:
            try:
                ttl = int(getattr(settings, "RETRIEVAL_CACHE_TTL_SECONDS", 600) or 600)
                ttl = max(30, ttl)
                cache_redis.set(
                    cache_key,
                    _serialize_docs_for_cache(docs).encode("utf-8"),
                    ex=ttl,
                    nx=True,
                )
            except Exception as e:
                logger.info(f"retrieval cache set failed: {e}")

    return docs or []


def get_citations_from_docs(docs, session: Session) -> list[dict]:
    """从检索结果构建引用信息"""
    citations = []
    for doc in docs:
        chunk_id = doc.metadata.get("chunk_id")
        document_id = doc.metadata.get("document_id")
        chunk = session.get(Chunk, chunk_id) if chunk_id else None

        source_name = doc.metadata.get("source", "")
        if document_id and not source_name:
            db_doc = session.get(Document, document_id)
            if db_doc:
                source_name = db_doc.title

        snippet = doc.page_content[:200] + ("..." if len(doc.page_content) > 200 else "")

        citations.append(
            {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "source": source_name,
                "page_no": chunk.page_no if chunk else doc.metadata.get("page"),
                "snippet": snippet,
            }
        )
    return citations


def hydrate_citations_from_stored(session: Session, stored) -> list[dict]:
    """从 Answer.citations 还原完整引用（兼容仅存 chunk_id 的旧数据）。"""
    if not stored:
        return []
    if isinstance(stored, str):
        try:
            stored = json.loads(stored)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(stored, list):
        return []

    out: list[dict] = []
    for item in stored:
        if not isinstance(item, dict):
            continue
        chunk_id = item.get("chunk_id")
        if not chunk_id:
            continue
        if item.get("snippet"):
            out.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": item.get("document_id"),
                    "page_no": item.get("page_no"),
                    "snippet": item["snippet"],
                    "source": item.get("source"),
                }
            )
            continue
        chunk = session.get(Chunk, chunk_id)
        if not chunk:
            continue
        document_id = chunk.document_id
        source_name = (item.get("source") or "").strip()
        if document_id and not source_name:
            db_doc = session.get(Document, document_id)
            if db_doc:
                source_name = (db_doc.title or "").strip()
        content = chunk.content or ""
        snippet = content[:200] + ("..." if len(content) > 200 else "")
        out.append(
            {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "page_no": chunk.page_no,
                "snippet": snippet,
                "source": source_name or None,
            }
        )
    return out


def build_prompt(
    history_text: str,
    context: str,
    question: str,
    *,
    target_document: str | None = None,
) -> str:
    prompt = """
    你是 DocPaws，一个基于文档的助手。请严格基于下方文档内容回答问题。
    """
    if target_document:
        prompt += f"""
本次检索已限定在文档「{target_document}」内，下方片段均来自该文档。
请据此作答；只要片段中有可用信息就必须回答，禁止称该文档不存在或不在范围内。
"""
    if history_text:
        prompt += """你可以参考历史对话来理解用户意图，但回答必须基于文档内容。

历史对话：
{history_text}

"""
    prompt += """
相关文档：
{context}

用户问题：
{question}
"""
    return prompt.format(history_text=history_text, context=context, question=question)


async def _stream_answer_impl(
    session: Session,
    *,
    kb_id: str,
    question: str,
    conversation_id: str | None,
    request_id: str,
    user_id: str,
    cache_redis: redis.Redis | None,
    document_id: str | None = None,
    folder_id: str | None = None,
    chat_mode: ChatMode = "fast",
) -> AsyncGenerator[dict, None]:
    """
    SSE 流式问答生成器（实现体，由 ChatService.stream_answer 转发）

    Yields:
        SSE payload dicts（type/content/finished/message_id/citations）
    """
    cfg = get_default_config()
    model_name = resolve_chat_model(cfg.get("model"))
    search_k = int(cfg.get("search_k", 5) or 5)

    # 1. 知识库归属
    try:
        require_kb_owned(session, kb_id, user_id)
    except AppError as e:
        yield {"type": "error", "code": e.error_code, "content": e.message}
        return

    # 2. 获取激活的索引产物
    artifact = get_active_index_artifact(session, kb_id)
    if not artifact:
        yield {"type": "answer_chunk", "content": "索引未就绪", "finished": True, "message_id": "", "citations": []}
        return

    from docpaws.usecases.chat_scope import (
        SCOPE_FOLDER,
        build_faiss_filter,
        document_ids_for_scope,
        resolve_effective_scope,
        scope_cache_token,
        scope_from_request,
        validate_scope,
    )

    # 3. 创建/获取会话（尽早返回 conversation_id，便于前端直达会话详情）
    cid = conversation_id
    conv: Conversation | None = None
    if cid:
        conv = get_conversation_by_id(session, cid)
        if not conv:
            cid = None
        elif conv.user_id != user_id or conv.kb_id != kb_id:
            yield {"type": "error", "code": ErrorCode.FORBIDDEN, "content": "无权访问该会话"}
            return

    scope_type, scope_id = resolve_effective_scope(
        conversation=conv,
        document_id=document_id,
        folder_id=folder_id,
    )
    try:
        validate_scope(session, kb_id=kb_id, scope_type=scope_type, scope_id=scope_id)
    except AppError as e:
        yield {"type": "error", "code": e.error_code, "content": e.message}
        return

    if not cid:
        new_scope_type, new_scope_id = scope_from_request(
            document_id=document_id, folder_id=folder_id
        )
        conv = create_conversation(
            session,
            kb_id,
            user_id,
            question[:30],
            scope_type=new_scope_type,
            scope_id=new_scope_id,
        )
        cid = conv.id
        scope_type, scope_id = new_scope_type, new_scope_id

    # 4. 保存用户消息（即便后续检索/生成失败，也保留用户提问记录）
    user_msg = Message(conversation_id=cid, role="user", content=question)
    session.add(user_msg)
    session.commit()
    session.refresh(user_msg)

    # 5. meta：立刻把 conversation_id 发给前端
    yield {
        "type": "meta",
        "request_id": request_id,
        "conversation_id": cid,
        "question_message_id": user_msg.id,
    }

    doc_ids = document_ids_for_scope(
        session, kb_id=kb_id, scope_type=scope_type, scope_id=scope_id
    )
    if doc_ids is not None and len(doc_ids) == 0:
        empty_msg = (
            "该文件夹下暂无可检索文档"
            if scope_type == SCOPE_FOLDER
            else "当前范围内暂无可检索内容"
        )
        yield {
            "type": "answer_chunk",
            "content": empty_msg,
            "request_id": request_id,
            "finished": True,
            "conversation_id": cid,
            "message_id": "",
            "citations": [],
        }
        return

    metadata_filter = build_faiss_filter(doc_ids)
    scope_token = scope_cache_token(scope_type, scope_id)
    artifact_id = getattr(artifact, "id", "") or str(getattr(artifact, "version", ""))

    # 6. 构建向量库（工具内检索使用）
    try:
        _, vectorstore = build_retriever(artifact.index_path)
    except FileNotFoundError:
        yield {
            "type": "error",
            "code": "INDEX_FILE_NOT_FOUND",
            "content": "索引文件不存在",
            "request_id": request_id,
            "finished": True,
            "conversation_id": cid,
        }
        return

    history_text = get_recent_history_text(session, cid, limit=10)
    scope_label = scope_prompt_label(
        session, kb_id=kb_id, scope_type=scope_type, scope_id=scope_id
    )

    if chat_mode == "deep":
        scope_doc_count = count_documents_in_scope(
            session, kb_id=kb_id, scope_type=scope_type, scope_id=scope_id
        )
        async for think_delta in stream_thinking_prelude(
            model_name=model_name,
            question=question,
            history_text=history_text,
            scope_label=scope_label,
            doc_count=scope_doc_count,
        ):
            if think_delta:
                yield {
                    "type": "thinking_chunk",
                    "content": think_delta,
                    "request_id": request_id,
                    "finished": False,
                }

    from docpaws.usecases.chat_scope import (
        retrieval_cache_scope_token,
        retrieval_filter_for_question,
    )

    if not should_skip_retrieval_preflight(question):
        pre_meta, pre_named_doc = retrieval_filter_for_question(
            session,
            kb_id=kb_id,
            scope_type=scope_type,
            scope_id=scope_id,
            base_filter=metadata_filter,
            text=question,
        )
        preflight_docs = retrieve_scoped_docs_cached(
            kb_id=kb_id,
            question=question,
            search_k=search_k,
            metadata_filter=pre_meta,
            vectorstore=vectorstore,
            cache_redis=cache_redis,
            artifact_id=artifact_id,
            scope_token=retrieval_cache_scope_token(scope_token, pre_named_doc),
        )
        if not preflight_docs:
            reject_msg = INSUFFICIENT_RETRIEVAL_MSG
            answer = Answer(
                conversation_id=cid,
                question_message_id=user_msg.id,
                version=1,
                is_current=True,
                answer_text=reject_msg,
                citations=[],
                model_name=model_name,
            )
            session.add(answer)
            session.commit()
            session.refresh(answer)
            assistant_msg = Message(
                conversation_id=cid,
                role="assistant",
                content=reject_msg,
                answer_id=answer.id,
            )
            session.add(assistant_msg)
            session.commit()
            session.refresh(assistant_msg)
            yield {
                "type": "answer_chunk",
                "content": reject_msg,
                "request_id": request_id,
                "finished": True,
                "conversation_id": cid,
                "message_id": assistant_msg.id,
                "answer_id": answer.id,
                "citations": [],
            }
            return

    from docpaws.usecases.chat_agent_tools import AgentToolContext
    from docpaws.usecases.chat_agent_runner import run_agent_stream

    tool_ctx = AgentToolContext(
        session=session,
        kb_id=kb_id,
        scope_type=scope_type,
        scope_id=scope_id,
        vectorstore=vectorstore,
        metadata_filter=metadata_filter,
        search_k=search_k,
        cache_redis=cache_redis,
        artifact_id=artifact_id,
        scope_token=scope_token,
        model_name=model_name,
        chat_mode=chat_mode,
    )

    llm = create_chat_llm(model_name=model_name, chat_mode=chat_mode)

    full: list[str] = []
    try:
        async for delta in run_agent_stream(
            llm=llm,
            ctx=tool_ctx,
            question=question,
            history_text=history_text,
        ):
            if delta:
                full.append(delta)
                yield {
                    "type": "answer_chunk",
                    "content": delta,
                    "request_id": request_id,
                    "finished": False,
                }
    except Exception as e:
        logger.exception(f"agent stream failed: {e}")
        yield {
            "type": "error",
            "code": "RETRIEVAL_FAILED",
            "content": "对话服务暂时不可用",
            "request_id": request_id,
            "finished": True,
            "conversation_id": cid,
        }
        return

    answer_text = "".join(full)
    citations = tool_ctx.last_citations

    if tool_ctx.last_hit_chunks:
        retrieval_run = RetrievalRun(
            kb_id=kb_id,
            conversation_id=cid,
            question_message_id=user_msg.id,
            query_text=question,
            top_k=search_k,
            hit_chunks=tool_ctx.last_hit_chunks,
        )
        session.add(retrieval_run)

    # 12. 保存答案 & 助手消息（同一个 session 内完成，避免事务边界混乱）
    answer = Answer(
        conversation_id=cid,
        question_message_id=user_msg.id,
        version=1,
        is_current=True,
        answer_text=answer_text,
        citations=[
            {
                "chunk_id": c.get("chunk_id"),
                "document_id": c.get("document_id"),
                "page_no": c.get("page_no"),
                "snippet": c.get("snippet"),
                "source": c.get("source"),
            }
            for c in citations
        ],
        model_name=model_name,
    )
    session.add(answer)
    session.commit()
    session.refresh(answer)

    assistant_msg = Message(
        conversation_id=cid,
        role="assistant",
        content=answer_text,
        answer_id=answer.id,
    )
    session.add(assistant_msg)
    session.commit()
    session.refresh(assistant_msg)

    # 13. 完成事件
    yield {
        "type": "answer_chunk",
        "content": "",
        "request_id": request_id,
        "finished": True,
        "conversation_id": cid,
        "message_id": assistant_msg.id,
        "answer_id": answer.id,
        "citations": citations,
    }


class ChatService:
    def __init__(self, session: Session, cache_redis: redis.Redis | None = None):
        self.session = session
        self.cache_redis = cache_redis

    def ensure_kb_and_index_ready(self, *, kb_id: str, user_id: str) -> None:
        from docpaws.infra.repos.document_repo import has_any_document, has_any_chunk
        from docpaws.infra.repos.index_repo import get_active_index_artifact

        require_kb_owned(self.session, kb_id, user_id)

        # 没有任何文档：空知识库
        if not has_any_document(self.session, kb_id):
            raise AppError(
                error_code=ErrorCode.KB_EMPTY,
                message="知识库为空",
                status_code=get_status_code(ErrorCode.KB_EMPTY),
                user_hint=ERROR_CODE_TO_HINT.get(ErrorCode.KB_EMPTY),
                details={"kb_id": kb_id},
            )    

        # 有文档但没有任何 chunks（例如扫描版/空白 PDF，解析不到文本）：
        # 对用户来说等价于“没有可检索内容”，在提问时提示 KB_EMPTY 即可。
        if not has_any_chunk(self.session, kb_id):
            raise AppError(
                error_code=ErrorCode.KB_EMPTY,
                message="知识库没有可检索内容",
                status_code=get_status_code(ErrorCode.KB_EMPTY),
                user_hint=ERROR_CODE_TO_HINT.get(ErrorCode.KB_EMPTY),
                details={"kb_id": kb_id},
            )

        if not get_active_index_artifact(self.session, kb_id):
            raise AppError(
                error_code=ErrorCode.INDEX_NOT_READY,
                message="索引未就绪，请先上传并索引文档",
                status_code=get_status_code(ErrorCode.INDEX_NOT_READY),
                user_hint=ERROR_CODE_TO_HINT.get(ErrorCode.INDEX_NOT_READY),
                details={"kb_id": kb_id},
            )

    def stream_answer(
        self,
        *,
        kb_id: str,
        question: str,
        conversation_id: str | None,
        request_id: str,
        user_id: str,
        document_id: str | None = None,
        folder_id: str | None = None,
        chat_mode: ChatMode = "fast",
    ):
        return _stream_answer_impl(
            self.session,
            kb_id=kb_id,
            question=question,
            conversation_id=conversation_id,
            request_id=request_id,
            user_id=user_id,
            cache_redis=self.cache_redis,
            document_id=document_id,
            folder_id=folder_id,
            chat_mode=chat_mode,
        )
