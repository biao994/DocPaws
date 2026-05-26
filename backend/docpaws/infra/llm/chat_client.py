"""
ChatOpenAI 封装：超时/重试/统一调用接口

对外提供稳定的 LLM 调用能力。
"""
from typing import Optional

from langchain_openai import ChatOpenAI

from docpaws.config import get_default_config


def create_chat_llm(model_name: Optional[str] = None, temperature: float = 0.1):
    """
    创建 ChatOpenAI 实例

    Args:
        model_name: 模型名称，默认从配置读取
        temperature: 温度参数
    """
    config = get_default_config()
    return ChatOpenAI(
        model=model_name or config.get("model", "deepseek-v4-flash"),
        temperature=temperature,
        timeout=config.get("llm_timeout", 30),
        api_key=config["llm_api_key"],
        base_url=config["llm_base_url"],
    )
