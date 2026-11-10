from src.rag.document_loader import Document
from src.rag.vector_store import SREVectorStore

def test_vector_store_add_and_search():
    store = SREVectorStore(persist_directory=None)
    doc1 = Document(
        doc_id="doc-oom",
        content="Pod was killed with exit code 137 OOMKilled when memory limit reached.",
        metadata={"doc_type": "postmortem"}
    )
    doc2 = Document(
        doc_id="doc-db",
        content="Database connection timeout on PostgreSQL connection pool.",
        metadata={"doc_type": "postmortem"}
    )
    
    store.add_documents([doc1, doc2])
    results = store.search("exit code 137 OOMKilled", top_k=1)
    
    assert len(results) > 0
    assert results[0]["doc_id"] == "doc-oom"
