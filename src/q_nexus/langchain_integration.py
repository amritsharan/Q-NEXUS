# pyrefly: ignore-errors
import os
import warnings
from typing import List

# Override showwarning to completely suppress deprecation, langchain and user warnings
_old_showwarning = warnings.showwarning
def _new_showwarning(message, category, filename, lineno, file=None, line=None):
    cat_name = category.__name__ if category else ""
    if "deprecation" in cat_name.lower() or "userwarning" in cat_name.lower() or "langchain" in cat_name.lower():
        return
    _old_showwarning(message, category, filename, lineno, file, line)
warnings.showwarning = _new_showwarning

warnings.filterwarnings("ignore")

# pyrefly: ignore [missing-import]
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
# pyrefly: ignore [missing-import]
from langchain.text_splitter import RecursiveCharacterTextSplitter
# pyrefly: ignore [missing-import]
from langchain.schema import Document
# pyrefly: ignore [missing-import]
from langchain.chains import RetrievalQA

try:
    # On Vercel, we force the use of SimpleVectorStore to keep the bundle size small.
    if os.environ.get("VERCEL"):
        raise ImportError("Forced SimpleVectorStore on Vercel")
    from langchain_community.vectorstores import Chroma
    HAS_CHROMA = True
except ImportError:
    Chroma = None
    HAS_CHROMA = False

import pickle
import numpy as np

class SimpleVectorStore:
    def __init__(self, persist_directory: str, embedding_function):
        self.persist_directory = persist_directory
        self.embedding_function = embedding_function
        self.db_file = os.path.join(persist_directory, "simple_vectors.pkl")
        self.documents = []
        self.embeddings = []
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, "rb") as f:
                    data = pickle.load(f)
                    self.documents = data.get("documents", [])
                    self.embeddings = data.get("embeddings", [])
            except Exception as e:
                print(f"Error loading simple vector store: {e}")

    def save(self):
        os.makedirs(self.persist_directory, exist_ok=True)
        with open(self.db_file, "wb") as f:
            pickle.dump({
                "documents": self.documents,
                "embeddings": self.embeddings
            }, f)

    @classmethod
    def from_documents(cls, documents, embedding_function, persist_directory):
        instance = cls(persist_directory, embedding_function)
        texts = [doc.page_content for doc in documents]
        embeddings = embedding_function.embed_documents(texts)
        instance.documents = documents
        instance.embeddings = embeddings
        instance.save()
        return instance

    def similarity_search(self, query: str, k: int = 4):
        if not self.embeddings:
            return []
        query_vector = self.embedding_function.embed_query(query)
        q_vec = np.array(query_vector)
        emb_matrix = np.array(self.embeddings)
        dot_products = np.dot(emb_matrix, q_vec)
        norms = np.linalg.norm(emb_matrix, axis=1) * np.linalg.norm(q_vec)
        norms = np.where(norms == 0, 1e-9, norms)
        similarities = dot_products / norms
        top_k_indices = np.argsort(similarities)[::-1][:k]
        return [self.documents[idx] for idx in top_k_indices]

    def as_retriever(self):
        class SimpleRetriever:
            def __init__(self, store):
                self.store = store
            def get_relevant_documents(self, query: str):
                return self.store.similarity_search(query)
            def invoke(self, input_data: str | dict, *args, **kwargs):
                query = input_data if isinstance(input_data, str) else input_data.get("query", "")
                return self.get_relevant_documents(query)
        return SimpleRetriever(self)


def init_openai_api(api_key: str | None = None) -> str:
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise EnvironmentError("OPENAI_API_KEY not set in environment or configuration")
    return key


def load_files_from_dir(source_dir: str, extensions: List[str] = None) -> List[Document]:
    if extensions is None:
        extensions = [".py", ".md", ".txt"]
    docs: List[Document] = []
    for root, dirs, files in os.walk(source_dir):
        # Prevent searching inside virtual environments, git, and database folders
        dirs[:] = [d for d in dirs if d not in (".venv", "venv", ".git", "chroma_store", "__pycache__")]
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


def create_chroma_store(source_dir: str, persist_directory: str = "./chroma_store", api_key: str | None = None):
    key = init_openai_api(api_key)
    docs = load_files_from_dir(source_dir)
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    split_docs = splitter.split_documents(docs)
    embeddings = OpenAIEmbeddings(api_key=key)
    if HAS_CHROMA and Chroma is not None:
        vectordb = Chroma.from_documents(split_docs, embeddings, persist_directory=persist_directory)
        if hasattr(vectordb, "persist"):
            vectordb.persist()
        return vectordb
    else:
        return SimpleVectorStore.from_documents(split_docs, embeddings, persist_directory=persist_directory)


def get_retriever(persist_directory: str = "./chroma_store", api_key: str | None = None):
    key = init_openai_api(api_key)
    embeddings = OpenAIEmbeddings(api_key=key)
    if HAS_CHROMA and Chroma is not None:
        vectordb = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
        return vectordb.as_retriever()
    else:
        db_file = os.path.join(persist_directory, "simple_vectors.pkl")
        if not os.path.exists(db_file):
            raise FileNotFoundError("SimpleVectorStore pkl file not found")
        vectordb = SimpleVectorStore(persist_directory=persist_directory, embedding_function=embeddings)
        return vectordb.as_retriever()


def answer_query(query: str, retriever, model_name: str = "gpt-4o-mini", api_key: str | None = None) -> str:
    key = init_openai_api(api_key)
    llm = ChatOpenAI(model_name=model_name, temperature=0, api_key=key)
    qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever)
    res = qa.invoke({"query": query})
    return res["result"]


if __name__ == "__main__":
    # quick local test: index this repo and ask a sample question
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    print("Indexing repo at", repo_root)
    try:
        create_chroma_store(repo_root)
        r = get_retriever()
        print(answer_query("What does src/q_nexus/pipeline.py do?", r))
    except Exception as exc:
        print("Langchain local run failed:", exc)
