"""
对话 Agent 工具：范围由后端注入，模型只选择调用哪条工具。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import redis
from langchain_core.tools import tool
from sqlmodel import Session

from docpaws.usecases.chat_scope import (
    count_documents_in_scope,
    document_title_for_id,
    list_document_titles_in_scope,
    resolve_document_id_from_question,
    retrieval_cache_scope_token,
    retrieval_filter_for_question,
    scope_prompt_label,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentToolContext:
    session: Session
    kb_id: str
    scope_type: str
    scope_id: str | None
    vectorstore: Any
    metadata_filter: dict | Any | None
    search_k: int
    cache_redis: redis.Redis | None
    artifact_id: str
    scope_token: str
    model_name: str
    chat_mode: str = "fast"
    last_citations: list[dict] = field(default_factory=list)
    last_hit_chunks: list[dict] = field(default_factory=list)


def build_agent_system_prompt(ctx: AgentToolContext) -> str:
    scope_label = scope_prompt_label(
        ctx.session,
        kb_id=ctx.kb_id,
        scope_type=ctx.scope_type,
        scope_id=ctx.scope_id,
    )
    return f"""你是 DocPaws 智能文档助手。当前对话已锁定在以下范围，不可切换知识库或文件夹：
{scope_label}

## 工具（按问题类型选择，勿向用户暴露工具名）
1. **count_scope_documents** — 统计当前范围内有多少个文件/文档（如「有几个文件」「多少份文档」）
2. **list_scope_documents** — 列出当前范围内的文档标题（如「有哪些文件」「列一下文档」）
3. **lookup_scope_document** — 按名称在当前范围内查找某个文档是否存在（完整扫描，不限 20 条）
4. **query_knowledge_base** — 基于文档内容理解并回答问题（如「是什么」「怎么样」「主要内容」）
5. **search_documents** — 按关键词在文档中查找原文片段（用户明确说「搜索/查找/找某个词」时用）

## 规则
- 问数量 → count_scope_documents；问有哪些文件 → list_scope_documents
- 用户问**某个具体文档**的内容、摘要、页码等 → **直接** query_knowledge_base，不要先用 list 判断是否存在
- list_scope_documents 最多显示 20 条，**不能**据此断定某个文件名不存在
- 若 query_knowledge_base 已返回正文，最终回复必须基于该内容，**禁止**再说「未找到该文档」
- 仅当用户要搜具体关键词时用 search_documents
- 回答使用中文，简洁准确；若工具无结果，如实说明
"""


def build_chat_agent_tools(ctx: AgentToolContext) -> list:
    """构建闭包注入范围后的工具列表。"""

    @tool
    def count_scope_documents() -> str:
        """统计当前对话范围内有多少个文档/文件。用于「有几个文件」「多少份文档」等问题。"""
        n = count_documents_in_scope(
            ctx.session,
            kb_id=ctx.kb_id,
            scope_type=ctx.scope_type,
            scope_id=ctx.scope_id,
        )
        label = scope_prompt_label(
            ctx.session,
            kb_id=ctx.kb_id,
            scope_type=ctx.scope_type,
            scope_id=ctx.scope_id,
        )
        return f"{label}内共有 {n} 个文档。"

    @tool
    def list_scope_documents(limit: int = 20) -> str:
        """列出当前范围内的文档标题。limit 为最多返回条数（默认 20）。"""
        cap = max(1, min(int(limit or 20), 50))
        titles = list_document_titles_in_scope(
            ctx.session,
            kb_id=ctx.kb_id,
            scope_type=ctx.scope_type,
            scope_id=ctx.scope_id,
            limit=cap,
        )
        if not titles:
            return "当前范围内没有文档。"
        lines = "\n".join(f"- {t}" for t in titles)
        return (
            f"共 {len(titles)} 个文档（最多显示 {cap} 个，可能未包含全部文件）：\n{lines}\n"
            "提示：判断某个文件名是否存在请用 lookup_scope_document，问文档内容请用 query_knowledge_base。"
        )

    @tool
    def lookup_scope_document(name_hint: str) -> str:
        """在当前范围内按名称查找文档是否存在（扫描全部文档，不受 list 条数限制）。"""
        hint = (name_hint or "").strip()
        if not hint:
            return "请提供要查找的文档名称。"
        doc_id = resolve_document_id_from_question(
            ctx.session,
            kb_id=ctx.kb_id,
            scope_type=ctx.scope_type,
            scope_id=ctx.scope_id,
            text=hint,
        )
        if not doc_id:
            return f"在当前范围内未找到名称匹配「{hint}」的文档。"
        title = document_title_for_id(ctx.session, doc_id) or doc_id
        return f"已找到文档：{title}"

    @tool
    def query_knowledge_base(question: str) -> str:
        """基于当前范围内已索引的文档内容回答问题。适合需要理解、解释、总结的问题。"""
        from docpaws.usecases.chat_service import (
            INSUFFICIENT_RETRIEVAL_MSG,
            build_prompt,
            get_citations_from_docs,
            hit_chunks_from_docs,
            retrieve_scoped_docs_cached,
        )
        from docpaws.usecases.chat_llm import create_chat_llm

        q = (question or "").strip()
        if not q:
            return "问题不能为空。"

        meta_filter, named_doc_id = retrieval_filter_for_question(
            ctx.session,
            kb_id=ctx.kb_id,
            scope_type=ctx.scope_type,
            scope_id=ctx.scope_id,
            base_filter=ctx.metadata_filter,
            text=q,
        )
        docs = retrieve_scoped_docs_cached(
            kb_id=ctx.kb_id,
            question=q,
            search_k=ctx.search_k,
            metadata_filter=meta_filter,
            vectorstore=ctx.vectorstore,
            cache_redis=ctx.cache_redis,
            artifact_id=ctx.artifact_id,
            scope_token=retrieval_cache_scope_token(ctx.scope_token, named_doc_id),
        )
        if not docs:
            return INSUFFICIENT_RETRIEVAL_MSG

        ctx.last_citations = get_citations_from_docs(docs, ctx.session)
        ctx.last_hit_chunks = hit_chunks_from_docs(docs)

        context_str = "\n\n".join(d.page_content for d in docs)
        target_title = document_title_for_id(ctx.session, named_doc_id)
        prompt = build_prompt("", context_str, q, target_document=target_title)
        llm = create_chat_llm(model_name=ctx.model_name, chat_mode=ctx.chat_mode)
        try:
            resp = llm.invoke(prompt)
            text = getattr(resp, "content", None) or str(resp)
            text = text.strip() or "未能生成回答。"
            if target_title:
                return f"【文档：{target_title}】\n{text}"
            return text
        except Exception as e:
            logger.exception("query_knowledge_base LLM failed: %s", e)
            return "生成回答时出错，请稍后重试。"

    @tool
    def search_documents(keyword: str) -> str:
        """在当前范围内按关键词检索文档原文片段（向量相似度）。适合「搜索/查找/找某个词」。"""
        from docpaws.usecases.chat_service import (
            get_citations_from_docs,
            hit_chunks_from_docs,
            retrieve_docs_with_retry,
        )

        kw = (keyword or "").strip().strip("\"'“”‘’")
        if not kw:
            return "关键词不能为空。"

        meta_filter, named_doc_id = retrieval_filter_for_question(
            ctx.session,
            kb_id=ctx.kb_id,
            scope_type=ctx.scope_type,
            scope_id=ctx.scope_id,
            base_filter=ctx.metadata_filter,
            text=kw,
        )
        try:
            docs = retrieve_docs_with_retry(
                ctx.vectorstore,
                kw,
                search_k=ctx.search_k,
                metadata_filter=meta_filter,
            )
        except Exception as e:
            logger.exception("search_documents failed: %s", e)
            return f"搜索失败：{e}"

        if not docs:
            return f"未找到与「{kw}」相关的文档片段。"

        ctx.last_citations = get_citations_from_docs(docs, ctx.session)
        ctx.last_hit_chunks = hit_chunks_from_docs(docs)

        parts: list[str] = []
        for i, doc in enumerate(docs[:5], 1):
            source = doc.metadata.get("source", "未知来源")
            content = (doc.page_content or "").strip()
            highlighted = re.sub(
                re.escape(kw),
                f"【{kw}】",
                content,
                flags=re.IGNORECASE,
            )
            parts.append(f"[{i} - {source}]\n{highlighted}")
        return f"找到 {len(docs)} 条相关片段（显示前 {min(5, len(docs))} 条）：\n\n" + "\n\n".join(
            parts
        )

    return [
        count_scope_documents,
        list_scope_documents,
        lookup_scope_document,
        query_knowledge_base,
        search_documents,
    ]
