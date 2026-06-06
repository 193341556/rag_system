from celery import Celery
from app.services.document_parser import split_document
from app.services.embedder import Embedder
from app.services.vector_store import VectorStore
from app.services.retriever import build_bm25_index
import psycopg2

celery_app = Celery('tasks', broker='redis://localhost:6379/0')
#celery_app = Celery('tasks', broker='redis://redis:6379/0')
def update_doc_status(doc_id: str, status: str, chunk_count: int = 0):
    conn = psycopg2.connect(
        host="localhost", port=5432,
        #host="postgres", port=5432,
        dbname="ragdb", user="raguser", password="ragpass"
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE documents SET status=%s, chunk_count=%s WHERE id=%s::uuid",
                (status, chunk_count, doc_id)
            )
        conn.commit()
    finally:
        conn.close()

@celery_app.task(bind=True, max_retries=3)
def process_document(self, doc_id: str, file_path: str):
    try:
        update_doc_status(doc_id, 'processing')
        chunks = split_document(file_path)
        embedder = Embedder()
        store = VectorStore(doc_id)
        store.add(chunks, embedder)
        store.save()
        build_bm25_index(doc_id, chunks)
        update_doc_status(doc_id, 'ready', chunk_count=len(chunks))
    except Exception as exc:
        update_doc_status(doc_id, 'failed')
        raise self.retry(exc=exc, countdown=30)