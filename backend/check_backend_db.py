#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

from app.vectorstore.metadata_db import Document, get_session

db = get_session()

# Show all documents
all_docs = db.query(Document).all()
print(f"Total documents in DB: {len(all_docs)}\n")

for doc in all_docs:
    print(f"File: {doc.file_path}")
    print(f"Status: {doc.status}")
    print(f"Error: {doc.error_message}")
    print(f"Updated: {doc.updated_at}")
    print(f"Chunks: {doc.total_chunks}")
    print("-" * 80)
