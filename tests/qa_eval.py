
import sys
sys.path.insert(0, '.')

from app.services.embedder import Embedder
from app.services.vector_store import VectorStore
from app.services.retriever import HybridRetriever

questions = [
    # BM25 优势：表格里的精确数字，向量检索语义不匹配
    ('What is RAG-Token EM score on WQ dataset?', '46.5'),
    ('What is RAG-Sequence EM score on CT dataset?', '53.4'),
    ('What is RAG-Token-BM25 score on NQ?', '29.7'),
    ('What is RAG-Sequence-Frozen score on TQA?', '52.1'),
    ('What BLEU score did BART achieve on Jeopardy?', '15.1'),
    ('What is the Rouge-L score of RAG-Sequence on MSMARCO?', '40.8'),
    ('What percentage accuracy did RAG get using 2016 index?', '70'),
    ('How many training examples does MS-MARCO have?', '153726'),
    ('How many test examples does FEVER-3-way have?', '10000'),
    ('How many parameters does DPR encoder have?', '110M'),

    # 向量检索优势：语义理解
    ('How does RAG avoid making up facts?', 'factual'),
    ('What makes RAG more reliable than BART?', 'hallucinate'),
    ('How does RAG handle questions without clear answers?', 'parametric'),
    ('What is the benefit of keeping the document encoder fixed?', 'costly'),
    ('Why does RAG outperform extractive models?', 'verbatim'),
    ('How does RAG update world knowledge?', 'replace'),
    ('What problem does retrieval collapse cause?', 'ignore'),
    ('Why is non-parametric memory interpretable?', 'human-readable'),
    ('How does RAG marginalize over documents?', 'latent'),
    ('What is the key advantage of end-to-end training?', 'jointly'),
]

DOC_ID = "58b4b866-2428-4986-8e64-dfc1a5c6d65f"
embedder = Embedder()

class VecRetriever:
    def __init__(self, doc_id, embedder):
        self.store = VectorStore(doc_id)
        self.embedder = embedder
    def retrieve(self, question, top_k=5):
        query_vec = self.embedder.encode([question])[0]
        return self.store.search(query_vec, top_k=top_k)

def eval_retriever(retriever, questions):
    hits = 0
    misses = []
    for q, keyword in questions:
        results = retriever.retrieve(q, top_k=5)
        matched = any(keyword.lower() in r.page_content.lower() for r in results)
        if matched:
            hits += 1
        else:
            misses.append(q)
    return hits / len(questions), misses

vec_retriever    = VecRetriever(DOC_ID, embedder)
hybrid_retriever = HybridRetriever(DOC_ID, embedder)

vec_acc,    vec_misses    = eval_retriever(vec_retriever,    questions)
hybrid_acc, hybrid_misses = eval_retriever(hybrid_retriever, questions)

print(f"纯向量 top-5 准确率:  {vec_acc:.0%}  ({int(vec_acc*20)}/20)")
print(f"混合检索 top-5 准确率: {hybrid_acc:.0%}  ({int(hybrid_acc*20)}/20)")
print(f"提升: +{(hybrid_acc - vec_acc):.0%}")
print(f"\n混合检索未命中: {hybrid_misses}")
