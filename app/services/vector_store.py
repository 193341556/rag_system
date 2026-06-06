import faiss
import numpy as np
import pickle


class VectorStore:
    def __init__(self, doc_id: str):
        self.doc_id = doc_id
        self.index = faiss.IndexFlatL2(1024)
        self.chunks = []
        # 如果索引文件存在，自动加载
        try:
            self.index = faiss.read_index(f"data/{doc_id}.faiss")
            with open(f"data/{doc_id}.pkl", "rb") as f:
                self.chunks = pickle.load(f)
        except (FileNotFoundError, RuntimeError):
            pass

    def add(self, chunks, embedder):
        texts = [c.page_content for c in chunks]
        vecs = embedder.encode(texts)
        self.index.add(np.array(vecs).astype("float32"))
        self.chunks.extend(chunks)

    def save(self):
        faiss.write_index(self.index, f"data/{self.doc_id}.faiss")
        with open(f"data/{self.doc_id}.pkl", "wb") as f:
            pickle.dump(self.chunks, f)

    def search(self, query_vec, top_k=5):
        _, ids = self.index.search(
            np.array([query_vec]).astype("float32"), top_k
        )
        return [self.chunks[i] for i in ids[0]]