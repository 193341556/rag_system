# app/services/retriever.py
from rank_bm25 import BM25Okapi
import pickle, numpy as np
from app.services.vector_store import VectorStore
from app.services.embedder import Embedder

def build_bm25_index(doc_id: str, chunks: list):
    tokenized = [c.page_content.split() for c in chunks]
    bm25 = BM25Okapi(tokenized)
    with open(f'data/{doc_id}.bm25.pkl', 'wb') as f:
        pickle.dump(bm25, f)
    return bm25

def load_bm25_index(doc_id: str):
    with open(f'data/{doc_id}.bm25.pkl', 'rb') as f:
        return pickle.load(f)
    
def reciprocal_rank_fusion(vec_ids, bm25_ids, k=60):
    """RRF：score = sum(1 / (k + rank))，rank 从 0 开始"""
    scores = {}
    for rank, idx in enumerate(vec_ids):
        scores[idx] = scores.get(idx, 0) + 1 / (k + rank + 1)
    for rank, idx in enumerate(bm25_ids):
        scores[idx] = scores.get(idx, 0) + 1 / (k + rank + 1)
    return sorted(scores, key=scores.get, reverse=True)
class HybridRetriever:
    def __init__(self, doc_id: str, embedder: Embedder):
        self.store   = VectorStore(doc_id)
        self.bm25    = load_bm25_index(doc_id)
        self.chunks  = self.store.chunks
        self.embedder = embedder

    def retrieve(self, question: str, top_k: int = 5):
        # 1. 向量检索 top-10
        query_vec = self.embedder.encode([question])[0]
        _, vec_ids = self.store.index.search(
            np.array([query_vec]).astype('float32'), 10
        )
        vec_ids = vec_ids[0].tolist()

        # 2. BM25 检索 top-10
        scores = self.bm25.get_scores(question.split())
        bm25_ids = np.argsort(scores)[::-1][:10].tolist()

        # 3. RRF 融合，取 top_k
        fused = reciprocal_rank_fusion(vec_ids, bm25_ids)[:top_k]
        return [self.chunks[i] for i in fused]