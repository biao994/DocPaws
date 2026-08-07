"""You.com Search API 客户端。

外部 I/O 层（见 AGENTS.md 规则 9）：调用 You.com Search API
（GET https://ydc-index.io/v1/search，X-API-Key 鉴权），把网页与新闻结果
归一化为 [{title, url, snippet}]，供 usecases 层的 search_web 工具编排。

API Key 取自 settings.YDC_API_KEY（环境变量 YDC_API_KEY，团队约定名）。
任何网络 / 状态码 / 解析异常都会被捕获并返回空结果，绝不向上抛出。
"""
from __future__ import annotations

import logging

import httpx

from docpaws.settings import settings

logger = logging.getLogger(__name__)

# You.com Search API 端点（团队约定）
YOUCOM_ENDPOINT = "https://ydc-index.io/v1/search"
# 团队约定：对 You.com 主机的请求需带此 User-Agent（lowercased owner-repo slug）
YOUCOM_USER_AGENT = "youdotcom-integration/biao994-docpaws"

MAX_COUNT = 20
REQUEST_TIMEOUT = 15.0


def web_search_available() -> bool:
    """是否已配置可用的 You.com API Key。"""
    return bool(settings.YDC_API_KEY)


def youcom_web_search(query: str, count: int | None = None) -> list[dict]:
    """调用 You.com Search API，返回归一化结果 [{title, url, snippet}]。

    未配置 Key、网络异常、非 2xx、解析失败时统一返回 []（记录日志，绝不抛出）。
    """
    api_key = settings.YDC_API_KEY
    if not api_key:
        logger.warning("web_search: 未配置 YDC_API_KEY，跳过联网检索")
        return []

    try:
        n = int(count) if count is not None else int(settings.YDC_WEB_SEARCH_COUNT)
    except (TypeError, ValueError):
        n = int(settings.YDC_WEB_SEARCH_COUNT)
    n = max(1, min(n, MAX_COUNT))

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            resp = client.get(
                YOUCOM_ENDPOINT,
                params={"query": query, "count": n},
                headers={"X-API-Key": api_key, "User-Agent": YOUCOM_USER_AGENT},
            )
    except httpx.HTTPError as exc:
        logger.error("You.com 联网检索请求失败: %s", exc)
        return []

    if resp.status_code != 200:
        # 不回显响应体，避免泄露账号信息；401 鉴权 / 429 限流 / 5xx 服务端
        logger.error("You.com 联网检索返回状态码 %s", resp.status_code)
        return []

    try:
        payload = resp.json()
    except ValueError as exc:
        logger.error("You.com 响应解析失败: %s", exc)
        return []

    return _normalize(payload, n)


def _normalize(payload: dict, n: int) -> list[dict]:
    """把 You.com 响应归一化为 [{title, url, snippet}]。

    响应结构 {"results": {"web": [...], "news": [...]}}；news 可能缺失，
    每条结果除 url/title/description/snippets 外字段均视为可选，防御式读取。
    web 与 news 各返回最多 n 条，按合并总数截断，与 count 语义对齐。
    """
    if not isinstance(payload, dict):
        return []
    results_node = payload.get("results")
    if not isinstance(results_node, dict):
        return []
    items: list[dict] = []
    for bucket in ("web", "news"):
        entries = results_node.get(bucket)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            snippets = entry.get("snippets")
            snippet_text = ""
            if isinstance(snippets, list):
                snippet_text = " ".join(s for s in snippets if isinstance(s, str))
            items.append({
                "title": entry.get("title") or "",
                "url": entry.get("url") or "",
                "snippet": entry.get("description") or snippet_text,
            })
    return items[:n]
