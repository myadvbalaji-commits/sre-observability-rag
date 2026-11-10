from pathlib import Path

from src.rag.document_loader import DocumentLoader


def test_parse_markdown_metadata():
    sample_md = """# Postmortem
- **Severity:** P1
- **Impacted Services:** checkout, billing
- **Duration:** 30m

## Summary
Test summary content.
"""
    meta = DocumentLoader.parse_markdown_metadata(sample_md)
    assert meta["severity"] == "P1"
    assert meta["impacted_services"] == "checkout, billing"
    assert meta["duration"] == "30m"

def test_load_sample_data():
    base_dir = Path(__file__).resolve().parent.parent / "sample_data"
    docs = DocumentLoader.load_all_sample_data(base_dir)
    assert len(docs) >= 3
    doc_types = {d.metadata.get("doc_type") for d in docs}
    assert "postmortem" in doc_types
    assert "runbook" in doc_types
