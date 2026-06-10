import pytest
from unittest.mock import AsyncMock, patch

FAKE_DOC_ID = "00000000-0000-0000-0000-000000000000"


@pytest.mark.anyio
class TestChat:

    async def test_ask_invalid_doc_id_returns_error(self, client, auth_headers):
        """doc_id 不存在时返回 404。"""
        resp = await client.post(
            "/api/chat/ask",
            params={"doc_id": FAKE_DOC_ID, "question": "什么是RAG？"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_ask_missing_doc_id(self, client, auth_headers):
        """缺少 doc_id 参数，返回 422。"""
        resp = await client.post(
            "/api/chat/ask",
            params={"question": "问题"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_ask_missing_question(self, client, auth_headers):
        """缺少 question 参数，返回 422。"""
        resp = await client.post(
            "/api/chat/ask",
            params={"doc_id": FAKE_DOC_ID},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_ask_cache_hit(self, client, auth_headers):
        """同一 doc_id + 同一问题，第二次请求 from_cache 为 True。"""
        with patch("app.routers.chat.resolve_doc_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.routers.chat.HybridRetriever") as MockRetriever, \
             patch("app.routers.chat.ask_llm", new_callable=AsyncMock) as mock_llm:

            mock_resolve.return_value = "cache-hit-doc-001"
            MockRetriever.return_value.retrieve.return_value = []
            mock_llm.return_value = "这是一个测试答案"

            doc_id = "cache-hit-doc-001"
            question = "缓存测试问题唯一标识abc"

            resp1 = await client.post(
                "/api/chat/ask",
                params={"doc_id": doc_id, "question": question},
                headers=auth_headers,
            )
            assert resp1.status_code == 200
            assert resp1.json()["from_cache"] is False

            resp2 = await client.post(
                "/api/chat/ask",
                params={"doc_id": doc_id, "question": question},
                headers=auth_headers,
            )
            assert resp2.status_code == 200
            assert resp2.json()["from_cache"] is True

    async def test_ask_cache_answer_consistent(self, client, auth_headers):
        """缓存命中时，返回的 answer 与第一次相同。"""
        with patch("app.routers.chat.resolve_doc_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.routers.chat.HybridRetriever") as MockRetriever, \
             patch("app.routers.chat.ask_llm", new_callable=AsyncMock) as mock_llm:

            mock_resolve.return_value = "cache-consistent-doc-002"
            MockRetriever.return_value.retrieve.return_value = []
            mock_llm.return_value = "固定答案内容xyz"

            doc_id = "cache-consistent-doc-002"
            question = "答案一致性测试唯一标识xyz"

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
        with patch("app.routers.chat.resolve_doc_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.routers.chat.HybridRetriever") as MockRetriever, \
             patch("app.routers.chat.ask_llm", new_callable=AsyncMock) as mock_llm:

            mock_resolve.return_value = "no-collision-doc-003"
            MockRetriever.return_value.retrieve.return_value = []
            mock_llm.side_effect = ["答案A", "答案B"]

            doc_id = "no-collision-doc-003"

            await client.post(
                "/api/chat/ask",
                params={"doc_id": doc_id, "question": "唯一问题A_nocollision"},
                headers=auth_headers,
            )
            resp2 = await client.post(
                "/api/chat/ask",
                params={"doc_id": doc_id, "question": "唯一问题B_nocollision"},
                headers=auth_headers,
            )
            assert resp2.json()["from_cache"] is False

    async def test_stream_missing_params(self, client, auth_headers):
        """/stream 缺少必要参数，返回 422。"""
        resp = await client.get(
            "/api/chat/stream",
            params={"question": "测试"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_stream_returns_event_stream(self, client, auth_headers):
        """/stream 正常调用返回 text/event-stream。"""
        with patch("app.routers.chat.resolve_doc_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.routers.chat.HybridRetriever") as MockRetriever, \
             patch("app.routers.chat.ask_llm_stream") as mock_stream:

            mock_resolve.return_value = "stream-doc-001"
            MockRetriever.return_value.retrieve.return_value = []

            async def fake_stream(*args, **kwargs):
                for token in ["这", "是", "流式", "回答"]:
                    yield token

            mock_stream.return_value = fake_stream()

            resp = await client.get(
                "/api/chat/stream",
                params={"doc_id": "stream-doc-001", "question": "流式测试问题"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")

    async def test_stream_response_contains_data(self, client, auth_headers):
        """/stream 响应体包含 SSE data 格式内容。"""
        with patch("app.routers.chat.resolve_doc_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.routers.chat.HybridRetriever") as MockRetriever, \
             patch("app.routers.chat.ask_llm_stream") as mock_stream:

            mock_resolve.return_value = "stream-doc-002"
            MockRetriever.return_value.retrieve.return_value = []

            async def fake_stream(*args, **kwargs):
                yield "测试内容"

            mock_stream.return_value = fake_stream()

            resp = await client.get(
                "/api/chat/stream",
                params={"doc_id": "stream-doc-002", "question": "内容测试"},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert b"data:" in resp.content

    async def test_rate_limit_triggers_on_11th_request(self, client, auth_headers):
        """连续发 11 次 /ask，第 11 次应返回 429。"""
        with patch("app.routers.chat.resolve_doc_id", new_callable=AsyncMock) as mock_resolve, \
             patch("app.routers.chat.HybridRetriever") as MockRetriever, \
             patch("app.routers.chat.ask_llm", new_callable=AsyncMock) as mock_llm:

            mock_resolve.return_value = "rate-limit-doc"
            MockRetriever.return_value.retrieve.return_value = []
            mock_llm.return_value = "答案"

            doc_id = "rate-limit-doc"
            status_codes = []
            for i in range(11):
                resp = await client.post(
                    "/api/chat/ask",
                    params={"doc_id": doc_id, "question": f"限流专用问题_{i}_unique"},
                    headers=auth_headers,
                )
                status_codes.append(resp.status_code)

            assert 429 in status_codes
