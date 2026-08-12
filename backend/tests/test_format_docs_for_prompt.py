"""回归：query 上下文必须带文件名，避免把同文档章节当成多份文档。"""
from langchain_core.documents import Document as LCDocument

from docpaws.usecases.chat_service import format_docs_for_prompt


def test_format_docs_for_prompt_includes_source_labels():
    docs = [
        LCDocument(
            page_content="第二部分 通用合同条款",
            metadata={"document_id": "d1", "source": "测试_V1.0"},
        ),
        LCDocument(
            page_content="第三部分 专用合同条款",
            metadata={"document_id": "d1", "source": "测试_V1.0"},
        ),
        LCDocument(
            page_content="国务院工作规则",
            metadata={"document_id": "d2", "source": "2023_PDF2"},
        ),
    ]
    ctx = format_docs_for_prompt(docs)
    assert "测试_V1.0" in ctx
    assert "2023_PDF2" in ctx
    assert "[1 - 测试_V1.0]" in ctx
    assert "[2 - 测试_V1.0]" in ctx
    assert "[3 - 2023_PDF2]" in ctx
    assert "第二部分 通用合同条款" in ctx
    # 裸拼正文（旧行为）不应出现：有正文却完全没有来源标注
    assert not ctx.startswith("第二部分")


def test_format_docs_for_prompt_fallback_unknown_source():
    docs = [LCDocument(page_content="hello", metadata={})]
    ctx = format_docs_for_prompt(docs)
    assert "[1 - 未知来源]" in ctx
    assert "hello" in ctx
