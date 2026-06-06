# ── 构建阶段 ────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# 先只复制依赖文件，充分利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── 运行阶段 ────────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# 复制已安装的依赖
COPY --from=builder /install /usr/local

# 复制项目代码
COPY . .

# 创建上传目录（容器内路径与 .env 中 UPLOAD_DIR 一致）
RUN mkdir -p /app/uploads

# 非 root 用户运行，提升安全性
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 生产建议用 --workers 2；开发时开 --reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
