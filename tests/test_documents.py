import io
import pytest


def _pdf_bytes() -> bytes:
    """最小合法 PDF，用于上传测试。"""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n9\n%%EOF"
    )


def _txt_bytes() -> bytes:
    return b"Hello, this is a plain text document for testing."


@pytest.mark.anyio
class TestDocumentUpload:

    # ── 正常流 ────────────────────────────────────────────────────────────

    async def test_upload_pdf_success(self, client, auth_headers):
        """上传合法 PDF，返回 202 和 task_id。"""
        resp = await client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=auth_headers,
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "task_id" in data
        assert "document_id" in data
        assert data["status"] == "pending"
        assert data["message"] != ""

    async def test_upload_txt_success(self, client, auth_headers):
        """上传合法 TXT，返回 202。"""
        resp = await client.post(
            "/api/documents/upload",
            files={"file": ("test.txt", io.BytesIO(_txt_bytes()), "text/plain")},
            headers=auth_headers,
        )
        assert resp.status_code == 202
        assert "task_id" in resp.json()

    async def test_upload_returns_task_id_immediately(self, client, auth_headers):
        """接口应立即返回，不等待处理完成（status 为 pending）。"""
        resp = await client.post(
            "/api/documents/upload",
            files={"file": ("quick.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=auth_headers,
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "pending"

    # ── 异常流 ────────────────────────────────────────────────────────────

    async def test_upload_invalid_extension(self, client, auth_headers):
        """上传 .exe 文件，返回 415。"""
        resp = await client.post(
            "/api/documents/upload",
            files={"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 415

    async def test_upload_invalid_extension_jpg(self, client, auth_headers):
        """上传 .jpg 文件，返回 415。"""
        resp = await client.post(
            "/api/documents/upload",
            files={"file": ("photo.jpg", b"\xff\xd8\xff", "image/jpeg")},
            headers=auth_headers,
        )
        assert resp.status_code == 415

    async def test_upload_without_auth(self, client):
        """不带 token 上传，返回 401。"""
        resp = await client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
        )
        assert resp.status_code == 401

    async def test_upload_oversized_file(self, client, auth_headers):
        """超过 50 MB 的文件，返回 413。"""
        large = b"x" * (51 * 1024 * 1024)
        resp = await client.post(
            "/api/documents/upload",
            files={"file": ("large.pdf", io.BytesIO(large), "application/pdf")},
            headers=auth_headers,
        )
        assert resp.status_code == 413

    # ── 任务状态查询 ──────────────────────────────────────────────────────

    async def test_task_status_exists(self, client, auth_headers):
        """上传后能用 task_id 查询到状态。"""
        upload_resp = await client.post(
            "/api/documents/upload",
            files={"file": ("status.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=auth_headers,
        )
        task_id = upload_resp.json()["task_id"]

        status_resp = await client.get(
            f"/api/documents/task/{task_id}",
            headers=auth_headers,
        )
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["task_id"] == task_id
        assert data["status"] in ("pending", "processing", "ready", "failed")

    async def test_task_status_not_found(self, client, auth_headers):
        """查询不存在的 task_id，返回 404。"""
        resp = await client.get(
            "/api/documents/task/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_task_status_without_auth(self, client):
        """不带 token 查询状态，返回 401。"""
        resp = await client.get(
            "/api/documents/task/00000000-0000-0000-0000-000000000000",
        )
        assert resp.status_code == 401

    # ── 文档列表 ──────────────────────────────────────────────────────────

    async def test_list_documents(self, client, auth_headers):
        """文档列表接口返回正确结构。"""
        resp = await client.get("/api/documents/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "items" in data
        assert "page" in data
        assert "page_size" in data

    async def test_list_documents_pagination(self, client, auth_headers):
        """分页参数生效：page=1&page_size=2。"""
        resp = await client.get(
            "/api/documents/?page=1&page_size=2",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["items"]) <= 2

    async def test_list_documents_without_auth(self, client):
        """不带 token 访问文档列表，返回 401。"""
        resp = await client.get("/api/documents/")
        assert resp.status_code == 401

    async def test_list_documents_invalid_page(self, client, auth_headers):
        """page=0 不合法，返回 422。"""
        resp = await client.get(
            "/api/documents/?page=0",
            headers=auth_headers,
        )
        assert resp.status_code == 422
