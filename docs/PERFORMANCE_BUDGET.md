# PERFORMANCE_BUDGET.md

All numbers here are targets until benchmarked. Never present them as measured production facts.

## Mandatory benchmark profiles
- 1,000 rows
- 10,000 rows
- full current government dataset

Record:
- CPU/RAM/GPU/VRAM
- OS/WSL2
- model ID + quantization
- batch size/concurrency
- embedding docs/s
- rerank pairs/s
- LLM tokens/s and requests/s
- P50/P95
- failure/retry rate
- Recall@K / Precision / Recall / F1

## First targets
- exact alias path: millisecond-class
- entity resolve without LLM P95 < 50ms/work order
- warm retrieval P95 < 100ms/query
- no-generative-LLM online path P95 < 500ms
- LLM path: seconds-class, measured by actual hardware

Do not optimize by deleting quality stages. Use batching, caching, candidate narrowing and durable jobs first.
