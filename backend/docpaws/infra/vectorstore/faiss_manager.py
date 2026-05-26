"""
FAISS 向量存储管理器

封装 FAISS 的创建/加载/检索/分块能力。
"""
import logging
import os
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

from docpaws.config import get_default_config

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """FAISS 向量存储管理器"""

    def __init__(self, config: dict | None = None):
        self.config = config or get_default_config()
        self.vectorstore: FAISS | None = None
        self.embeddings = OpenAIEmbeddings(
            model=self.config.get("embedding_model", "BAAI/bge-large-zh-v1.5"),
            chunk_size=self.config.get("embedding_chunk_size", 200),
            timeout=self.config.get("embedding_timeout", 120),
            api_key=self.config.get("embedding_api_key"),
            base_url=self.config.get("embedding_base_url"),
        )

    def split_documents(self, documents: List[Document]) -> List[Document]:
        """对文档进行智能分块"""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.get("chunk_size", 500),
            chunk_overlap=self.config.get("chunk_overlap", 100),
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", "、", ""]
        )
        texts = text_splitter.split_documents(documents)

        for idx, doc in enumerate(texts):
            doc.metadata["chunk_id"] = idx

        logger.info(f"文档分割完成，共 {len(texts)} 个文本块")
        return texts

    def create_vector_store(self, documents: List[Document], save_path: str) -> None:
        """创建向量数据库并保存"""
        if not documents:
            raise ValueError("文档列表不能为空")

        print(" 正在创建向量数据库...")
        self.vectorstore = FAISS.from_documents(documents, self.embeddings)
        os.makedirs(save_path, exist_ok=True)
        self.vectorstore.save_local(save_path)
        logger.info(f"向量数据库已保存到 {save_path}")
        print(" 向量数据库创建完成！")

    def load_vector_store(self, load_path: str) -> None:
        """加载已保存的向量数据库"""
        if not os.path.exists(f"{load_path}/index.faiss"):
            raise FileNotFoundError(f"向量数据库不存在: {load_path}")

        self.vectorstore = FAISS.load_local(
            load_path,
            self.embeddings,
            allow_dangerous_deserialization=True,
        )
        logger.info(f"已加载向量数据库: {load_path}")

    def get_retriever(self):
        """获取检索器"""
        if not self.vectorstore:
            raise ValueError("向量数据库未初始化，请先创建或加载")
        return self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": self.config.get("search_k", 5)},
        )
