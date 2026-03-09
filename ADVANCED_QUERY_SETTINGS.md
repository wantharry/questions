# Advanced Query Settings

The system now supports comprehensive query configuration to fine-tune retrieval and answer generation.

## Overview

Advanced query settings allow you to control every aspect of the retrieval pipeline, from initial search to final answer generation. These settings are accessible through the UI's "Advanced Query Settings" panel.

## Settings Categories

### 1. General Settings

#### Query Decomposition
- **Status**: Experimental (placeholder)
- **Purpose**: Breaks complex queries into multiple simpler sub-queries
- **When to use**: For multi-part questions or complex topics
- **Example**: "Explain quantum mechanics and its applications in computing" → Split into separate queries

#### Compose Sub-Answers
- **Status**: Experimental (placeholder)
- **Purpose**: Merges answers from decomposed sub-queries into a coherent response
- **Requires**: Query decomposition to be enabled
- **When to use**: With query decomposition for unified answers

#### Pruning
- **Status**: Experimental (placeholder)
- **Purpose**: Removes retrieved chunks that are irrelevant to the query
- **When to use**: When you want only highly relevant content
- **Trade-off**: May miss useful context

#### Verify Answer
- **Default**: Enabled
- **Purpose**: Validates answer quality before returning
- **When to use**: Always recommended for production
- **When to disable**: For speed in testing/development

#### Streaming
- **Status**: Not yet implemented
- **Purpose**: Stream response tokens as they're generated
- **When implemented**: Real-time answer generation

### 2. Retrieval Settings

#### LLM Selection
- **Options**: `qwen2.5:7b`, `qwen3:0.6b`, `llama3.2:3b`, Default
- **Purpose**: Choose which LLM to use for answer generation
- **Default**: Uses system default (configured in backend)
- **Recommendations**:
  - `qwen2.5:7b`: Best quality, slower
  - `qwen3:0.6b`: Fastest, good quality
  - `llama3.2:3b`: Alternative option

#### Search Type
- **Options**: `hybrid`, `vector`, `fts`
- **Default**: `hybrid` (recommended)
- **Purpose**: Determines retrieval strategy

**Hybrid** (Vector + FTS):
- Combines semantic vector search with keyword-based full-text search
- Best for: General purpose queries
- Pros: Handles both conceptual and specific queries
- Cons: Slightly slower than single mode

**Vector** (Semantic Only):
- Pure embedding-based semantic search
- Best for: Conceptual questions, finding similar ideas
- Pros: Understands meaning and context
- Cons: May miss exact keyword matches

**FTS** (Full-Text Search Only):
- Keyword-based BM25 search
- Best for: Exact phrase matching, specific terms
- Pros: Fast, precise for known keywords
- Cons: Doesn't understand semantic meaning

#### Retrieval Chunks
- **Range**: 5-50 chunks
- **Default**: 20
- **Purpose**: Number of chunks to retrieve initially
- **Recommendations**:
  - **5-10**: Fast, focused queries
  - **15-25**: General purpose (recommended)
  - **30-50**: Comprehensive search, complex topics

### 3. Reranking & Context

#### AI Reranker
- **Default**: Enabled
- **Purpose**: Uses cross-encoder model to rerank retrieved chunks
- **How it works**: 
  1. Initial retrieval gets candidates
  2. Reranker scores each chunk against the query
  3. Chunks are reordered by relevance
- **When to use**: Always recommended for best quality
- **When to disable**: For speed in testing

#### Reranker Top Chunks
- **Range**: 3-20 chunks
- **Default**: 10
- **Purpose**: Number of top chunks to keep after reranking
- **Relationship**: Must be ≤ Retrieval Chunks
- **Recommendations**:
  - **3-5**: Quick answers, single-topic queries
  - **8-12**: General purpose (recommended)
  - **15-20**: Comprehensive answers, research

#### Expand Context Window
- **Default**: Disabled
- **Purpose**: Includes surrounding chunks for each result
- **How it works**: Retrieves chunks before/after each match
- **When to use**: 
  - When chunks might be part of larger passages
  - For continuity in explanations
- **Trade-off**: More context but potentially less focused

#### Context Window Size
- **Range**: 0-5 chunks
- **Default**: 1 (per side)
- **Purpose**: Number of surrounding chunks to include
- **Example**: 
  - Size 0: Only the matched chunk
  - Size 1: 1 chunk before + matched + 1 after = 3 total
  - Size 2: 2 before + matched + 2 after = 5 total

## Usage Examples

### Example 1: Quick Factual Query

**Query**: "What is the speed of light?"

**Settings**:
```
Search Type: hybrid
Retrieval Chunks: 10
AI Reranker: Enabled
Reranker Top Chunks: 5
Expand Context: Disabled
```

**Rationale**: Simple question needs few high-quality chunks.

### Example 2: Complex Conceptual Question

**Query**: "Explain the relationship between special relativity and general relativity"

**Settings**:
```
Search Type: hybrid
Retrieval Chunks: 30
AI Reranker: Enabled
Reranker Top Chunks: 15
Expand Context: Enabled
Context Window: 2
```

**Rationale**: Complex topic needs comprehensive retrieval with context.

### Example 3: Keyword-Specific Search

**Query**: "Find all mentions of 'quantum entanglement'"

**Settings**:
```
Search Type: fts
Retrieval Chunks: 20
AI Reranker: Disabled (not needed for exact matches)
```

**Rationale**: Looking for specific term, FTS is more appropriate.

### Example 4: Research Deep Dive

**Query**: "What are the current theories about dark matter?"

**Settings**:
```
Search Type: hybrid
Retrieval Chunks: 50
AI Reranker: Enabled
Reranker Top Chunks: 20
Expand Context: Enabled
Context Window: 3
Verify Answer: Enabled
```

**Rationale**: Comprehensive research needs maximum retrieval and context.

## Performance Considerations

### Speed vs Quality Trade-offs

**Fastest Configuration**:
```
Search Type: vector
Retrieval Chunks: 5
AI Reranker: Disabled
Reranker Top Chunks: 3
Expand Context: Disabled
```
- Use for: Testing, development, simple queries
- Quality: Good for basic questions

**Balanced Configuration** (Recommended):
```
Search Type: hybrid
Retrieval Chunks: 20
AI Reranker: Enabled
Reranker Top Chunks: 10
Expand Context: Disabled
```
- Use for: Production, general queries
- Quality: Excellent for most use cases

**Maximum Quality Configuration**:
```
Search Type: hybrid
Retrieval Chunks: 50
AI Reranker: Enabled
Reranker Top Chunks: 20
Expand Context: Enabled
Context Window: 3
```
- Use for: Critical queries, research, complex topics
- Quality: Best possible results
- Speed: Slower (acceptable for important queries)

## API Usage

### Via REST API

```bash
curl -X POST "http://localhost:8601/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain quantum mechanics",
    "top_k": 5,
    "settings": {
      "query_decomposition": false,
      "compose_sub_answers": false,
      "pruning": false,
      "verify_answer": true,
      "streaming": false,
      "retrieval_llm": "qwen2.5:7b",
      "search_type": "hybrid",
      "retrieval_chunks": 20,
      "ai_reranker": true,
      "reranker_top_chunks": 10,
      "expand_context_window": false,
      "context_window_size": 1
    }
  }'
```

### Via Python SDK

```python
import requests

def query_with_settings(query, settings):
    response = requests.post(
        "http://localhost:8601/api/query",
        json={
            "query": query,
            "top_k": 5,
            "settings": settings
        }
    )
    return response.json()

# Example usage
settings = {
    "search_type": "hybrid",
    "retrieval_chunks": 20,
    "ai_reranker": True,
    "reranker_top_chunks": 10
}

result = query_with_settings("What is quantum mechanics?", settings)
print(result["answer"])
```

## Best Practices

### 1. Start with Defaults
Begin with the default settings (balanced configuration) and adjust based on results.

### 2. Match Settings to Query Type
- **Simple factual**: Lower retrieval chunks, fewer reranked chunks
- **Complex conceptual**: Higher retrieval, more reranked chunks, context expansion
- **Keyword search**: Use FTS search type
- **Semantic search**: Use vector or hybrid

### 3. Enable AI Reranker for Production
The reranker significantly improves result quality with minimal performance cost.

### 4. Use Context Window Sparingly
Only enable context expansion when you know chunks might be part of longer passages.

### 5. Monitor Performance
Track query times and adjust settings if performance becomes an issue.

### 6. Experiment with Your Data
Different document types and query patterns may benefit from different settings.

## Troubleshooting

### Issue: No relevant results

**Solutions**:
1. Increase `retrieval_chunks` to 30-50
2. Try different `search_type` (switch between hybrid/vector/fts)
3. Disable `pruning` if enabled
4. Enable `expand_context_window`

### Issue: Too many irrelevant results

**Solutions**:
1. Enable `ai_reranker` if disabled
2. Decrease `reranker_top_chunks` to 5-7
3. Enable `pruning`
4. Decrease `retrieval_chunks`

### Issue: Slow query performance

**Solutions**:
1. Decrease `retrieval_chunks` to 10-15
2. Decrease `reranker_top_chunks` to 5-7
3. Disable `expand_context_window`
4. Try `vector` search type instead of `hybrid`

### Issue: Answers lack context

**Solutions**:
1. Enable `expand_context_window`
2. Increase `context_window_size` to 2-3
3. Increase `reranker_top_chunks` to 15-20

## Future Enhancements

Planned features for advanced query settings:

- [ ] Query decomposition implementation
- [ ] Sub-answer composition
- [ ] Intelligent pruning algorithm
- [ ] Streaming response support
- [ ] Query planning and optimization
- [ ] Adaptive settings based on query complexity
- [ ] A/B testing framework for settings comparison
- [ ] Settings profiles (presets for common use cases)
- [ ] Settings recommendation engine
- [ ] Query performance analytics dashboard

## Related Documentation

- [MULTI_INDEX_GUIDE.md](MULTI_INDEX_GUIDE.md) - Multi-index feature documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture overview
- [backend/app/models.py](backend/app/models.py) - `AdvancedQuerySettings` model definition
- [backend/app/main.py](backend/app/main.py) - Query endpoint implementation

---

**Version**: 1.0  
**Last Updated**: March 2026  
**Compatibility**: Backend v1.0+, Frontend v2.0+
