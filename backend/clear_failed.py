#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

from app.vectorstore.metadata_db import Document, get_session

db = get_session()

# Delete all failed documents
failed_docs = db.query(Document).filter_by(status='failed').all()
print(f"Found {len(failed_docs)} failed documents")

for doc in failed_docs:
    print(f"Deleting: {doc.file_path}")
    db.delete(doc)

db.commit()
print("\nAll failed documents cleared!")
print("You can now retry ingestion.")
