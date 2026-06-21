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
from langchain_community.vectorstores import Chroma
# pyrefly: ignore [missing-import]
from langchain.chains import RetrievalQA


def init_openai_api(api_key: str | None = None) -> str:
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise EnvironmentError("OPENAI_API_KEY not set in environment or configuration")
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


def create_chroma_store(source_dir: str, persist_directory: str = "./chroma_store", api_key: str | None = None) -> Chroma:
    key = init_openai_api(api_key)
    docs = load_files_from_dir(source_dir)
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    split_docs = splitter.split_documents(docs)
    embeddings = OpenAIEmbeddings(api_key=key)
    vectordb = Chroma.from_documents(split_docs, embeddings, persist_directory=persist_directory)
    if hasattr(vectordb, "persist"):
        vectordb.persist()
    return vectordb


def get_retriever(persist_directory: str = "./chroma_store", api_key: str | None = None):
    key = init_openai_api(api_key)
    embeddings = OpenAIEmbeddings(api_key=key)
    vectordb = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
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
