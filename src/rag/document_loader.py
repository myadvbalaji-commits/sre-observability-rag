import os
import re
from pathlib import Path
from typing import List, Dict, Any

class Document:
    def __init__(self, doc_id: str, content: str, metadata: Dict[str, Any]):
        self.doc_id = doc_id
        self.content = content
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "metadata": self.metadata
        }

class DocumentLoader:
    """Parses SRE Postmortems, SOP Runbooks, and Alert definitions."""

    @staticmethod
    def parse_markdown_metadata(content: str) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        for line in content.splitlines():
            match = re.match(r"^[-*]\s+\*\*([^:]+):\*\*\s*(.+)$", line.strip())
            if match:
                key = match.group(1).strip().lower().replace(" ", "_")
                val = match.group(2).strip()
                metadata[key] = val
        return metadata

    @classmethod
    def load_directory(cls, dir_path: Path, doc_type: str) -> List[Document]:
        documents: List[Document] = []
        if not dir_path.exists():
            return documents

        for file_path in dir_path.glob("*.md"):
            with open(file_path, "r", encoding="utf-8") as f:
                raw_text = f.read()

            extracted_meta = cls.parse_markdown_metadata(raw_text)
            extracted_meta["doc_type"] = doc_type
            extracted_meta["filename"] = file_path.name
            extracted_meta["source"] = str(file_path)

            doc = Document(
                doc_id=file_path.stem,
                content=raw_text,
                metadata=extracted_meta
            )
            documents.append(doc)
        return documents

    @classmethod
    def load_all_sample_data(cls, base_sample_dir: Path) -> List[Document]:
        docs: List[Document] = []
        postmortem_dir = base_sample_dir / "postmortems"
        runbook_dir = base_sample_dir / "runbooks"

        docs.extend(cls.load_directory(postmortem_dir, doc_type="postmortem"))
        docs.extend(cls.load_directory(runbook_dir, doc_type="runbook"))
        return docs
