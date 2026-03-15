# ML Research Scenario: Compare Embedding Models for Semantic Search

Benchmark three embedding models (OpenAI text-embedding-3-small, sentence-transformers/all-MiniLM-L6-v2, and a fine-tuned in-house model) for semantic search quality and latency on our product catalogue dataset.

## Requirements

- Evaluate each model on a 1,000-query benchmark set with human-annotated relevance labels
- Metrics: NDCG@10, MRR@10, average latency per query (p50/p99)
- Run evaluations on the same hardware baseline to ensure fair comparison
- Produce a summary table and recommendation

## Acceptance Criteria

- [ ] All three models evaluated on the same benchmark dataset
- [ ] Results reproducible with a fixed random seed
- [ ] Recommendation includes trade-off analysis (quality vs latency vs cost)
