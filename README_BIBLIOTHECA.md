# Bibliotheca AI - Setup & Usage Guide

This module transforms your book collection (PDFs, EPUBs, Images) into an LLM-accessible database using Multimodal RAG and Knowledge Graphs.

## 1. Installation

Ensure you are in the project root:
```bash
pip install -r requirements.txt
```

## 2. Configuration

Create a `.env` file in the root directory with the following keys:

```bash
# Llama Cloud (for LlamaParse - OCR)
LLAMA_CLOUD_API_KEY=llx-your-key-here

# Neo4j (for Knowledge Graph)
NEO4J_URL=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# OpenAI (for Embeddings/LLM)
OPENAI_API_KEY=sk-your-key-here
```

## 3. Ingestion (The Librarian)

1.  Place your books (PDF, EPUB, Images) in the `data/` directory.
2.  Run the ingestion script:

```bash
python src/ingest.py --dir data
```

*Note: This will process files, extract text/images, run OCR via LlamaParse if needed, and populate both ChromaDB (local) and Neo4j.*

## 4. Usage (The Agent)

You can now use the `src.agent_tools` module to query your library.

```python
from src.agent_tools import query_library

response = query_library("What does this book say about AI architecture?")
print(response)
```

## Maintenance

*   **ChromaDB**: Stored locally in `./chroma_db`.
*   **Neo4j**: Managed via your Neo4j instance (Docker/Desktop).
