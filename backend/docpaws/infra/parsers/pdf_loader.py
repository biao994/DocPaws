"""
PDF 文档加载器

按页切分，metadata 中包含 source/page。
"""
import os
import logging
from typing import List

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def get_pdf_page_count(pdf_path: str) -> int:
    """获取 PDF 页数"""
    import fitz
    with fitz.open(pdf_path) as doc:
        return doc.page_count


def load_pdf_documents(pdf_path: str, source_name: str | None = None) -> List[Document]:
    """
    加载 PDF 为 Document 列表（按页）

    - 按页切割：page 是最稳定的定位点
    - 每页一个 Document，metadata 至少含 source/page
    - 空页自动跳过
    """
    import fitz

    if not os.path.exists(pdf_path):
        raise ValueError(f"PDF 文件不存在: {pdf_path}")

    source = source_name or pdf_path
    docs: List[Document] = []

    with fitz.open(pdf_path) as doc:
        for i in range(doc.page_count):
            page = doc.load_page(i)
            text = (page.get_text("text") or "").strip()
            if not text:
                continue  # 空页跳过，避免污染索引
            docs.append(Document(
                page_content=text,
                metadata={"source": source, "page": i + 1},
            ))

    if not docs:
        raise ValueError(f"PDF 文件 {pdf_path} 没有有效内容")
    return docs
