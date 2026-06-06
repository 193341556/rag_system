from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-m3")
#封装 Embedder 类
class Embedder:
    def __init__(self):
        self.model = SentenceTransformer("BAAI/bge-m3")

    def encode(self, texts: list[str], batch_size: int = 32) -> list:
        # batch_size 控制每次处理多少条，避免内存溢出
        return self.model.encode(texts, batch_size=batch_size, show_progress_bar=True)
if __name__ == "__main__":
    embedder = Embedder()
    vecs = embedder.encode(["什么是 RAG？", "机器学习是人工智能的子集"])
    print(vecs.shape)   # → (2, 1024)  每个文本变成 1024 维向量