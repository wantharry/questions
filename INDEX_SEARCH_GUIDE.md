# Index Search Guide

## How Indexes Are Separated

Your RAG system uses **5 specialized indexes** to organize different types of educational content:

### Index Types

| Index Name | Content Type | What's Stored |
|-----------|--------------|---------------|
| **theory** | Explanations & Concepts | Theories, definitions, theorems, conceptual explanations |
| **formula** | Mathematical Content | Formulas, equations, derivations, mathematical expressions |
| **exercise** | Practice Problems | Questions, exercises, practice problems, assignments |
| **solution** | Worked Examples | Step-by-step solutions, worked examples, problem-solving |
| **general** | Mixed Content | Tables, diagrams, summaries, unclassified content |

### How Content Gets Routed

During ingestion, the system automatically classifies each chunk of content and routes it to the appropriate index:

```
Document → Smart Chunker → Content Classifier → Appropriate Index
```

**Content Classification Mapping:**
- `theory`, `definition`, `theorem` → **theory** index
- `formula`, `derivation` → **formula** index  
- `exercise`, `question` → **exercise** index
- `worked_example`, `solution` → **solution** index
- `diagram`, `table`, `unknown` → **general** index

## Searching Indexes

### 1. Search All Indexes (Default Behavior)

**What happens:** The system automatically routes your query to the most relevant indexes using intelligent query analysis.

**When to use:** Most queries! The system is smart enough to:
- Identify if you're asking for a concept (searches `theory` index)
- Looking for a formula (searches `formula` index)
- Need practice problems (searches `exercise` index)
- Want examples (searches `solution` index)

**How to use in UI:**
1. Go to "Query & Questions" tab
2. Select **"All Indexes"** from dropdown
3. Enter your query

**Example queries:**
```
"Explain Newton's second law" → Routes to theory index
"What is the formula for kinetic energy?" → Routes to formula index  
"Show me thermodynamics problems" → Routes to exercise index
"How to solve quadratic equations?" → Routes to solution index
```

### 2. Search Specific Index

**What happens:** Only searches the specific index you select, ignoring others.

**When to use:**
- You know exactly what type of content you need
- Want to narrow down results to specific content types
- Comparing how different indexes respond to the same query

**How to use in UI:**
1. Go to "Query & Questions" tab
2. Select specific index from dropdown: `theory`, `formula`, `exercise`, `solution`, or `general`
3. Enter your query

**Example use cases:**

**Searching only theory index:**
```
Query: "momentum" in theory index
→ Returns explanations and definitions of momentum
→ Ignores formulas, problems, and solutions
```

**Searching only formula index:**
```
Query: "momentum" in formula index
→ Returns p = mv, impulse-momentum theorem, etc.
→ Ignores conceptual explanations
```

**Searching only exercise index:**
```
Query: "momentum" in exercise index
→ Returns practice problems about momentum
→ Ignores theory and formulas
```

### 3. Hybrid Search Strategy

The system combines two search methods:

1. **Dense Search (FAISS)**: Semantic similarity using embeddings
2. **Sparse Search (BM25)**: Keyword matching

**Weights:**
- Dense weight: 0.5 (semantic meaning)
- Sparse weight: 0.5 (keyword relevance)

**Reranking:**
- Uses cross-encoder to reorder results
- Brings most relevant chunks to the top

## In the UI

### Tab 1: Indexes

**View all indexes:**
- See the 5 default specialized indexes
- View statistics (document count, chunks, etc.)
- Inspect index details

### Tab 2: Add Documents  

**Upload to specific indexes:**
- You CAN'T directly choose which index to upload to
- Content is automatically classified and routed during ingestion
- The system decides based on content type

### Tab 3: Query & Questions

**Index selector dropdown:**
```
┌─────────────────────────┐
│ Search in Index:        │
├─────────────────────────┤
│ All Indexes        <--  │ Default: Smart routing to all
│ default                 │ Same as "All Indexes"
│ theory                  │ Only theory/explanations  
│ formula                 │ Only formulas/equations
│ exercise                │ Only problems/questions
│ solution                │ Only worked examples
│ general                 │ Only mixed content
└─────────────────────────┘
```

## Backend Implementation

### Query Routing Logic

```python
# When index_name is None or "All Indexes"
→ Uses QueryRouter to analyze intent
→ Recommends best indexes for query
→ Searches recommended indexes with weighted fusion

# When specific index_name is provided
→ Maps name to IndexType enum
→ Searches only that index
→ Returns focused results</example>
```

### Index Name Mapping

```python
index_mapping = {
    "theory": IndexType.THEORY,
    "formula": IndexType.FORMULA,
    "exercise": IndexType.EXERCISE,
    "solution": IndexType.SOLUTION,
    "general": IndexType.GENERAL,
}
```

## Advanced Query Settings

### Retrieval Settings

- **Retrieval chunks**: How many chunks to retrieve (5-50)
- **AI Reranker**: Use cross-encoder for better ranking
- **Reranker top chunks**: Final number after reranking (3-20)

### Index-Specific Tips

**For theory index:**
- Use conceptual queries: "explain", "what is", "define"
- Higher retrieval chunks (20-30) for comprehensive explanations

**For formula index:**
- Use direct formula names or symbols
- Lower retrieval chunks (5-10) for focused results

**For exercise index:**
- Use "problems", "exercises", "practice"
- Medium retrieval chunks (10-15)

**For solution index:**
- Use "solve", "how to", "example"
- Medium retrieval chunks (10-15)

## Statistics & Monitoring

Check your current index stats:

```bash
# Via UI: Tab 1 → Click any index → View details
# Via API: GET http://localhost:8601/api/indexes
```

**Example stats:**
```json
{
  "indexes": [{
    "index_name": "theory",
    "index_type": "theory",
    "is_default": true,
    "stats": {
      "vectors": 55885,
      "documents": 45,
      "dimension": 384
    }
  }]
}
```

## Best Practices

### ✅ DO

- **Use "All Indexes" for most queries** - The router is intelligent
- **Use specific indexes when you need focused results**
- **Enable AI reranker** for better relevance
- **Adjust retrieval chunks** based on query complexity

### ❌ DON'T

- Don't search specific indexes unless you have a clear reason
- Don't disable reranking for important queries
- Don't use too few retrieval chunks (< 10) for complex queries
- Don't expect custom index creation to work differently than default routing

## Troubleshooting

**Problem: Not getting expected results**
- Try "All Indexes" first to see what the router finds
- Then try specific indexes to narrow down
- Check if content was properly classified during ingestion

**Problem: Results from wrong index**
- Content classification might have categorized it differently
- Check document metadata for actual content_type
- Some content legitimately spans multiple categories

**Problem: Want to force specific index during upload**
- Not currently supported (automatic classification only)
- Workaround: Use advanced query settings to search specific indexes

## API Examples

### Search All Indexes

```bash
curl -X POST http://localhost:8601/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is momentum?",
    "top_k": 10,
    "index_name": null
  }'
```

### Search Specific Index

```bash
curl -X POST http://localhost:8601/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "momentum formula",
    "top_k": 5,
    "index_name": "formula"
  }'
```

### With Advanced Settings

```bash
curl -X POST http://localhost:8601/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "momentum",
    "top_k": 10,
    "index_name": "theory",
    "settings": {
      "ai_reranker": true,
      "retrieval_chunks": 20,
      "reranker_top_chunks": 10
    }
  }'
```

## Summary

- ✅ **Yes, you CAN search all indexes!** (It's the default)
- ✅ **Content is automatically separated** by type into 5 indexes
- ✅ **Query routing is intelligent** and recommends best indexes
- ✅ **You can override** and search specific indexes if needed
- ✅ **Hybrid search** combines semantic + keyword matching
- ✅ **Reranking ensures** best results come first

The system is designed to "just work" with smart defaults, but gives you control when you need it.
