from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter





def split_document(documentname: str):
    loader = PyMuPDFLoader(documentname)
    pages = loader.load()



    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=64,
        separators=["\n\n", "\n", "。", "！", "？", " "]
    )
    print(f"读取到 {len(pages)} 页") 
    chunks = splitter.split_documents(pages)
    
    return chunks

print(split_document("test.pdf"))