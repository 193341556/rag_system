import pytest
from unittest.mock import AsyncMock, patch


# 固定一个不存在的 doc_id，用于测试错误场景
FAKE_DOC_ID = "00000000-0000-0000-0000-000000000000"


@pytest.mark.anyio
class TestChat:

    # ── /ask 正常流 ───────────────────────────────────────────────────────

    async def test_ask_without_auth(self, client):
        """/ask 不带 token，返回 401。"""
        resp = await client.post(
            "/api/chat/ask",
            params={"doc_id": FAKE_DOC_ID, "question": "测试问题"},
        )
        assert resp.status_code == 401

    async def test_ask_invalid_doc_id_returns_error(self, client, auth_headers):
        """doc_id 不存在时，HybridRetriever 加载索引失败，返回 4xx/5xx 而非 200。"""
        resp = await client.post(
            "/api/chat/ask",
            params={"doc_id": FAKE_DOC_ID, "question": "什么是RAG？"},
            headers=auth_headers,
        )
        # 不存在的 doc_id 应该触发错误，不应返回 200
        assert resp.status_code != 200

    async def test_ask_empty_question_returns_error(self, client, auth_headers):
        """空问题字符串，应返回错误（422 或业务错误）。"""
        resp = await client.post(
            "/api/chat/ask",
            params={"doc_id": FAKE_DOC_ID, "question": ""},
            headers=auth_headers,
        )
        assert resp.status_code in (400, 422, 500)

    # ── 缓存命中 ──────────────────────────────────────────────────────────

    async def test_ask_cache_hit(self, client, auth_headers):
        """同一 doc_id + 同一问题，第二次请求 from_cache 为 True。"""
        mock_chunks = []

        # mock HybridRetriever 和 ask_llm，避免依赖真实索引文件和 LLM API
        with patch(
            "app.routers.chat.HybridRetriever"
        ) as MockRetriever, patch(
            "app.routers.chat.ask_llm", new_callable=AsyncMock
        ) as mock_llm:
            MockRetriever.return_value.retrieve.return_value = mock_chunks
            mock_llm.return_value = "这是一个测试答案"

            doc_id = "test-cache-doc-001"
            question = "缓存测试问题"

            # 第一次请求：不走缓存
            resp1 = await client.post(
                "/api/chat/ask",
                params={"doc_id": doc_id, "question": question},
                headers=auth_headers,
            )
            assert resp1.status_code == 200
            assert resp1.json()["from_cache"] is False

            # 第二次请求：命中缓存
            resp2 = await client.post(
                "/api/chat/ask",
                params={"doc_id": doc_id, "question": question},
                headers=auth_headers,
            )
            assert resp2.status_code == 200
            assert resp2.json()["from_cache"] is True

    async def test_ask_cache_answer_consistent(self, client, auth_headers):
        """缓存命中时，返回的 answer 与第一次相同。"""
        with patch(
            "app.routers.chat.HybridRetriever"
        ) as MockRetriever, patch(
            "app.routers.chat.ask_llm", new_callable=AsyncMock
        ) as mock_llm:
            MockRetriever.return_value.retrieve.return_value = []
            mock_llm.return_value = "固定答案内容"

            doc_id = "test-cache-doc-002"
            question = "答案一致性测试"

            resp1 = await client.post(
                "/api/chat/ask",
                params={"doc_id": doc_id, "question": question},
                headers=auth_headers,
            )
            resp2 = await client.post(
                "/api/chat/ask",
                params={"doc_id": doc_id, "question": question},
                headers=auth_headers,
            )
            assert resp1.json()["answer"] == resp2.json()["answer"]

    async def test_ask_different_questions_no_cache_collision(self, client, auth_headers):
        """不同问题不应命中同一缓存。"""
        with patch(
            "app.routers.chat.HybridRetriever"
        ) as MockRetriever, patch(
            "app.routers.chat.ask_llm", new_callable=AsyncMock
        ) as mock_llm:
            MockRetriever.return_value.retrieve.return_value = []
            mock_llm.side_effect = ["答案A", "答案B"]

            doc_id = "test-cache-doc-003"

            resp1 = await client.post(
                "/api/chat/ask",
                params={"doc_id": doc_id, "question": "问题A"},
                headers=auth_headers,
            )
            resp2 = await client.post(
                "/api/chat/ask",
                params={"doc_id": doc_id, "question": "问题B"},
                headers=auth_headers,
            )
            # 两个不同问题，第二次不应命中第一次的缓存
            assert resp2.json()["from_cache"] is False

    # ── /stream 接口 ──────────────────────────────────────────────────────

    async def test_stream_without_auth(self, client):
        """/stream 不带 token，返回 401。"""
        resp = await client.get(
            "/api/chat/stream",
            params={"doc_id": FAKE_DOC_ID, "question": "测试"},
        )
        assert resp.status_code == 401

    async def test_stream_returns_event_stream(self, client, auth_headers):
        """/stream 返回 Content-Type: text/event-stream。"""
        with patch(
            "app.routers.chat.HybridRetriever"
        ) as MockRetriever, patch(
            "app.routers.chat.ask_llm_stream"
        ) as mock_stream:
            MockRetriever.return_value.retrieve.return_value = []

            async def fake_stream(*args, **kwargs):
                for token in ["这", "是", "流式", "回答"]:
                    yield token

            mock_stream.return_value = fake_stream()

            resp = await client.get(
                "/api/chat/stream",
                params={"doc_id": "stream-doc-001", "question": "流式测试"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")

    # ── 限流 ─────────────────────────────────────────────────────────────

    async def test_rate_limit_triggers_on_11th_request(self, client, auth_headers):
        """连续发 11 次 /ask，第 11 次应返回 429。"""
        with patch(
            "app.routers.chat.HybridRetriever"
        ) as MockRetriever, patch(
            "app.routers.chat.ask_llm", new_callable=AsyncMock
        ) as mock_llm:
            MockRetriever.return_value.retrieve.return_value = []
            mock_llm.return_value = "答案"

            doc_id = "rate-limit-doc"
            status_codes = []
            for i in range(11):
                resp = await client.post(
                    "/api/chat/ask",
                    params={"doc_id": doc_id, "question": f"问题{i}"},
                    headers=auth_headers,
                )
                status_codes.append(resp.status_code)

            # 前10次正常，第11次触发限流
            assert all(c == 200 for c in status_codes[:10])
            assert status_codes[10] == 429
