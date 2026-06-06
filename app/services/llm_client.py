import json
import asyncio
import httpx
from app.config import get_settings
from app.services.embedder import Embedder
from app.services.vector_store import VectorStore
from app.services.document_parser import split_document

settings = get_settings()

async def ask_llm(question: str, context: str) -> str:
    prompt = f"""根据以下文档内容回答问题，只根据文档内容作答，不要编造信息。

文档内容：
{context}

问题：{question}"""

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.llm_api_url,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={
                "model": "glm-4-flash",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        return resp.json()["choices"][0]["message"]["content"]



async def ask_llm_stream(question: str, context: str):
    """流式调用 LLM，逐 token yield"""
    prompt = f'根据文档内容回答问题：\n{context}\n\n问题：{question}'
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            'POST', settings.llm_api_url,
            headers={'Authorization': f'Bearer {settings.llm_api_key}'},
            json={
                'model': settings.llm_model,
                'messages': [{'role': 'user', 'content': prompt}],
                'stream': True
            }
        ) as resp:
            async for line in resp.aiter_lines():
                if line.startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        break
                    chunk = json.loads(data)
                    content = chunk['choices'][0]['delta'].get('content', '')
                    if content:
                        yield content


