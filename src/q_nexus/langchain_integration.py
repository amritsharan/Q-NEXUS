import os
from typing import List

from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQA


def init_openai_api():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise EnvironmentError("OPENAI_API_KEY not set in environment")
    return key


def load_files_from_dir(source_dir: str, extensions: List[str] = None) -> List[Document]:
    if extensions is None:
        extensions = [".py", ".md", ".txt"]
    docs: List[Document] = []
    for root, _, files in os.walk(source_dir):
        for fname in files:
            if any(fname.endswith(ext) for ext in extensions):
                path = os.path.join(root, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        text = f.read()
                    docs.append(Document(page_content=text, metadata={"source": path}))
                except Exception:
                    continue
    return docs


def create_chroma_store(source_dir: str, persist_directory: str = "./chroma_store") -> Chroma:
    init_openai_api()
    docs = load_files_from_dir(source_dir)
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    split_docs = splitter.split_documents(docs)
    embeddings = OpenAIEmbeddings()
    vectordb = Chroma.from_documents(split_docs, embeddings, persist_directory=persist_directory)
    vectordb.persist()
    return vectordb


def get_retriever(persist_directory: str = "./chroma_store", embedding: OpenAIEmbeddings | None = None):
    init_openai_api()
    embedding = embedding or OpenAIEmbeddings()
    vectordb = Chroma(persist_directory=persist_directory, embedding_function=embedding)
    return vectordb.as_retriever()


def answer_query(query: str, retriever, model_name: str = "gpt-4o-mini") -> str:
    llm = ChatOpenAI(model_name=model_name, temperature=0)
    qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever)
    return qa.run(query)


if __name__ == "__main__":
    # quick local test: index this repo and ask a sample question
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    print("Indexing repo at", repo_root)
    create_chroma_store(repo_root)
    r = get_retriever()
    print(answer_query("What does src/q_nexus/pipeline.py do?", r))
