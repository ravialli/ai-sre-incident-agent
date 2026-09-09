from pathlib import Path
from typing import Any

import yaml
from langchain_core.documents import Document

def parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith('---'):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    yaml_content = parts[1]
    body = parts[2].lstrip('\r\n')
    metadata = yaml.safe_load(yaml_content) or {}

    if not isinstance(metadata, dict):
        metadata = {}

    return metadata, body

def load_runbooks(runbooks_dir: Path) -> list[Document]:
    documents: list[Document] = []
    if not runbooks_dir.exists():
        raise FileNotFoundError(f"Runbooks directory does not exist: {runbooks_dir}")
    if not runbooks_dir.is_dir():
        raise NotADirectoryError(f"Runbooks path is not a directory: {runbooks_dir}")
    
    for file_path in sorted(runbooks_dir.glob("*.md")):
        content = file_path.read_text(encoding="utf-8")
        
        frontmatter, body = parse_frontmatter(content)
 
        metadata={
            # Trusted application metadata
            "source": str(file_path),
            "filename": file_path.name,
            "runbook_id": file_path.stem,
            "source_type": "local_markdown",
            "document_type": "runbook",
            "authoritative": False,

            # Runbook-declared metadata
            "runbook_title": frontmatter.get("title"),
            "category": frontmatter.get("category"),
            "services": frontmatter.get("services", []),
            "technologies": frontmatter.get("technologies", []),
            "severity": frontmatter.get("severity"),
            "declared_read_only": frontmatter.get("read_only"),
            "related": frontmatter.get("related", []),
        }
        document = Document(page_content=body, metadata=metadata)

        documents.append(document)

    return documents
