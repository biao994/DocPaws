"""infra/websearch/youcom_client 单元测试（离线，不触网、不需要真实 Key）。

用 httpx.MockTransport 打桩 You.com Search API，覆盖：来源映射、鉴权头与
User-Agent、count 夹取与总数截断、未配置 Key、各类错误（非 2xx / 网络异常 /
解析失败）优雅降级、异常响应结构不崩溃、Key 不泄露。

标准库 unittest，pytest 亦可收集；可 `python tests/test_youcom_websearch.py` 直跑。
"""
import unittest
from unittest import mock

import httpx

from docpaws.infra.websearch import youcom_client as yc
from docpaws.settings import settings

UA = "youdotcom-integration/biao994-docpaws"

SAMPLE = {
    "results": {
        "web": [
            {"url": "https://e.com/a", "title": "标题A", "description": "描述A",
             "snippets": ["片段A1", "片段A2"]},
            {"url": "https://e.com/b", "title": "标题B", "snippets": ["片段B1"]},
        ],
        "news": [
            {"url": "https://e.com/n", "title": "新闻N", "description": "新闻描述"},
        ],
    },
    "metadata": {"query": "t"},
}


def _mock_httpx(handler):
    """返回一个把 MockTransport 注入 httpx.Client 的替身工厂。"""
    real_client = httpx.Client

    def factory(*_args, **kwargs):
        return real_client(
            transport=httpx.MockTransport(handler), timeout=kwargs.get("timeout", 15)
        )
    return factory


class YouComClientTest(unittest.TestCase):

    def setUp(self):
        self._key_patch = mock.patch.object(settings, "YDC_API_KEY", "secret-key")
        self._key_patch.start()

    def tearDown(self):
        self._key_patch.stop()

    def test_available_reflects_key(self):
        self.assertTrue(yc.web_search_available())
        with mock.patch.object(settings, "YDC_API_KEY", ""):
            self.assertFalse(yc.web_search_available())

    def test_no_key_returns_empty_without_calling(self):
        with mock.patch.object(settings, "YDC_API_KEY", ""):
            with mock.patch.object(yc.httpx, "Client") as client:
                self.assertEqual(yc.youcom_web_search("q"), [])
                client.assert_not_called()

    def test_maps_web_and_news_with_headers(self):
        captured = {}

        def handler(request):
            captured["headers"] = request.headers
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, json=SAMPLE)

        with mock.patch.object(yc.httpx, "Client", _mock_httpx(handler)):
            out = yc.youcom_web_search("测试", count=5)

        self.assertEqual(len(out), 3)
        self.assertEqual(out[0], {
            "title": "标题A", "url": "https://e.com/a", "snippet": "描述A"})
        self.assertEqual(out[1]["snippet"], "片段B1")     # description 缺失回退 snippet
        self.assertEqual(out[2]["title"], "新闻N")        # news 也纳入
        self.assertEqual(captured["headers"]["X-API-Key"], "secret-key")
        self.assertEqual(captured["headers"]["User-Agent"], UA)
        self.assertEqual(captured["params"]["query"], "测试")
        self.assertEqual(captured["params"]["count"], "5")

    def test_count_clamped_and_total_truncated(self):
        body = {"results": {
            "web": [{"url": f"u{i}", "title": f"T{i}"} for i in range(4)],
            "news": [{"url": "un", "title": "N"}],
        }}
        seen = {}

        def handler(request):
            seen["count"] = request.url.params.get("count")
            return httpx.Response(200, json=body)

        with mock.patch.object(yc.httpx, "Client", _mock_httpx(handler)):
            yc.youcom_web_search("q", count=99)           # 99 → MAX_COUNT(20)
            self.assertEqual(seen["count"], "20")
            out = yc.youcom_web_search("q", count=3)       # web+news=5 → 截断为 3
            self.assertEqual(len(out), 3)

    def test_non_200_returns_empty_no_key_leak(self):
        def handler(request):
            return httpx.Response(500, text="server boom secret-key")

        with mock.patch.object(yc.httpx, "Client", _mock_httpx(handler)):
            out = yc.youcom_web_search("q")
        self.assertEqual(out, [])
        self.assertNotIn("secret-key", str(out))

    def test_network_error_returns_empty(self):
        def handler(request):
            raise httpx.ConnectError("boom")

        with mock.patch.object(yc.httpx, "Client", _mock_httpx(handler)):
            self.assertEqual(yc.youcom_web_search("q"), [])

    def test_bad_json_returns_empty(self):
        def handler(request):
            return httpx.Response(200, text="not-json{{")

        with mock.patch.object(yc.httpx, "Client", _mock_httpx(handler)):
            self.assertEqual(yc.youcom_web_search("q"), [])

    def test_non_dict_payloads_return_empty(self):
        # 顶层为 list/str，或 results 为非 dict：不得抛出，统一返回 []
        for body in ('[1, 2, 3]', '"oops"', '{"results": "oops"}', '{"results": [1]}'):
            def handler(request, _b=body):
                return httpx.Response(200, text=_b, headers={"content-type": "application/json"})
            with mock.patch.object(yc.httpx, "Client", _mock_httpx(handler)):
                self.assertEqual(yc.youcom_web_search("q"), [], body)

    def test_hostile_shapes_no_crash(self):
        body = {"results": {
            "web": ["str", 42, None, {"title": None, "url": None,
                                      "snippets": [None, "有效片段"]}],
            "news": "not-a-list",
        }}

        def handler(request):
            return httpx.Response(200, json=body)

        with mock.patch.object(yc.httpx, "Client", _mock_httpx(handler)):
            out = yc.youcom_web_search("q")
        self.assertEqual(len(out), 1)                     # 非 dict / 非法项被跳过
        self.assertEqual(out[0]["snippet"], "有效片段")


if __name__ == "__main__":
    unittest.main()
