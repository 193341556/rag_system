# RAG 智能文档问答系统

![CI](https://github.com/193341556/rag_system/actions/workflows/ci.yml/badge.svg)

基于 RAG（Retrieval-Augmented Generation）架构的智能文档问答系统。上传 PDF/TXT 文档，系统自动解析、切片、向量化，支持自然语言提问，通过混合检索找到最相关片段，结合 LLM 流式生成答案。

## 技术栈

| 层次           | 技术                           |
| ------------ | ---------------------------- |
| Web 框架       | FastAPI + uvicorn            |
| 数据库          | PostgreSQL（SQLAlchemy async） |
| 缓存 / 消息队列    | Redis                        |
| 异步任务         | Celery                       |
| 向量检索         | FAISS（IndexFlatL2，1024 维）    |
| 关键词检索        | BM25（rank-bm25）              |
| 融合策略         | RRF（Reciprocal Rank Fusion）  |
| Embedding 模型 | BAAI/bge-m3（本地，多语言）          |
| LLM          | GLM-4-Flash（智谱 AI）           |
| 认证           | JWT（python-jose + bcrypt）    |
| 限流           | slowapi（10 次/分钟/用户）          |
| 部署           | Docker Compose               |

## 项目结构

```
rag-system/
├── app/
│   ├── main.py                # FastAPI 入口，路由注册，生命周期
│   ├── config.py              # pydantic-settings 配置管理
│   ├── database.py            # SQLAlchemy 异步引擎与会话
│   ├── limiter.py             # slowapi 限流配置
│   ├── models/
│   │   ├── user.py            # User ORM 模型
│   │   └── document.py        # Document ORM 模型
│   ├── routers/
│   │   ├── auth.py            # 注册 / 登录 / JWT 验证
│   │   ├── documents.py       # 文档上传 / 状态查询 / 列表
│   │   └── chat.py            # 流式问答 / 普通问答 + 缓存
│   ├── services/
│   │   ├── embedder.py        # bge-m3 向量编码封装
│   │   ├── vector_store.py    # FAISS 索引管理（增删查保存）
│   │   ├── retriever.py       # 混合检索（FAISS + BM25 + RRF）
│   │   ├── document_parser.py # PyMuPDF 解析 + 文本分块
│   │   └── llm_client.py      # GLM-4-Flash 调用（流式 / 非流式）
│   ├── tasks/
│   │   └── document_tasks.py  # Celery 文档处理任务
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── requirements.txt
├── data/                      # FAISS 索引 + BM25 pkl（gitignore）
├── uploads/                   # 上传文件存储（gitignore）
├── tests/
│   ├── conftest.py
│   └── qa_eval.py             # 混合检索 vs 纯向量准确率评测
└── index.html                 # 前端单页应用（纯 HTML）
```

## 快速启动

### 前置依赖

- Python 3.11+
- Docker & Docker Compose
- （可选）4 GB+ 内存（bge-m3 模型约 2 GB）

### 1. 克隆并配置环境变量

```bash
git clone <repo-url>
cd rag-system
cp .env.example .env   # 填入 LLM_API_KEY 等配置
```

`.env` 关键配置项：

```env
DATABASE_URL=postgresql+asyncpg://raguser:ragpass@localhost:5432/ragdb
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<随机字符串>
LLM_API_KEY=<智谱 AI API Key>
LLM_API_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions
LLM_MODEL=glm-4-flash
EMBEDDING_MODEL=BAAI/bge-m3
```

### 2. 安装依赖

```bash
pip install -r app/requirements.txt
```

### 3. 启动基础服务（PostgreSQL + Redis）

```bash
docker compose -f app/docker-compose.yml up postgres redis -d
```

### 4. 启动 FastAPI

```bash
uvicorn app.main:app --reload
```

### 5. 启动 Celery Worker

```bash
celery -A app.tasks.document_tasks:celery_app worker --loglevel=info
```

### 6. 打开前端

浏览器访问 `index.html`（或直接打开文件），配置后端地址为 `http://localhost:8000`。

## API 接口

### 认证

```
POST /api/auth/register    # 注册，返回 user_id
POST /api/auth/login       # 登录，返回 JWT access_token（24h 有效）
```

### 文档管理

```
POST /api/documents/upload           # 上传 PDF/TXT，立即返回 task_id
GET  /api/documents/task/{task_id}   # 轮询处理状态（pending/processing/ready/failed）
GET  /api/documents/                 # 文档列表（分页）
```

### 问答

```
GET  /api/chat/stream    # SSE 流式问答（打字机效果）
POST /api/chat/ask       # 普通问答 + Redis 缓存（10 次/分钟限流）
```

#### 流式问答示例

```bash
curl -N "http://localhost:8000/api/chat/stream?doc_id=<id>&question=文档主要讲了什么"
```

返回：

```
data: {"type": "chunk", "content": "这"}
data: {"type": "chunk", "content": "篇文档"}
...
data: {"type": "done", "sources": [...]}
```

## 核心设计说明

### 为什么用 RAG 而不是 Fine-tuning

Fine-tuning 适合固定知识域；本系统每个用户上传不同文档，知识是动态的，RAG 无需重训练、可实时接入新文档。

### 混合检索（FAISS + BM25 + RRF）

纯向量检索在精确关键词匹配上较弱（如"第3.2节的公式"）；BM25 基于词频互补；RRF 融合无需手动调权重，鲁棒性好。

自建 20 条 QA 测试集的评测结果：

| 方案               | Top-5 准确率 |
| ---------------- | --------- |
| 纯向量检索            | 65%       |
| 混合检索（BM25 + RRF） | 70%       |

> 精确事实查询（如表格数字、章节编号）提升尤为明显。

### 异步文档处理

PDF 解析 + 向量化耗时 5–30 秒，同步处理会阻塞接口。Celery 将处理放入队列，接口立即返回 `task_id`，前端轮询状态，用户体验从等待 ~8s 降至 <200ms。

### Redis 问答缓存

缓存 key = `qa:{doc_id}:{md5(question)}`，TTL 1 小时。相同文档 + 相同问题直接命中缓存，跳过检索和 LLM 调用，重复问答响应时间 < 50ms。流式接口不走缓存。

### chunk_size 选 512

512 token ≈ 1–2 个自然段落，在检索粒度（够具体）和上下文完整性（不截断段落）之间取得平衡；overlap=64 防止关键信息被边界截断。

## 测试

```bash
# 运行接口测试（auth / documents / chat 三个模块，20+ 条用例）
pytest tests/ -v --cov=app --cov-report=term-missing

# 混合检索 vs 纯向量准确率对比
python tests/qa_eval.py

# 压测（需启动服务后运行）
locust -f tests/locustfile.py --host=http://localhost:8000
```

## 性能数据（Locust 压测，50 并发）

| 接口                       | P99 响应时间 | 错误率 |
| ------------------------ | -------- | --- |
| GET /api/documents/      | 12 ms    | 0%  |
| POST /api/chat/ask（缓存命中） | < 50 ms  | 0%  |

## 许可证

MIT
